"""
document_agent/app.py — Modern Flask UI for the Document Agent.

Run with:
    python document_agent/app.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import io
import re
import json
import hashlib
import uuid
import time

from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
from flask_socketio import SocketIO, emit

import pypdf
import docx
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from fpdf import FPDF
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from config import DOCUMENT_AGENT_CONFIG
from core.memory import Memory
from core.runner import run_agent

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())
socketio = SocketIO(app, cors_allowed_origins="*")

MAX_DOCUMENT_CHARS = 50_000
DEFAULT_FILENAME = "my_document.txt"
FONT_DIR = Path(__file__).resolve().parent / "fonts"

sessions: dict[str, dict] = {}


def get_session(sid: str) -> dict:
    if sid not in sessions:
        sessions[sid] = {
            "memory": Memory(),
            "thinking": [],
            "last_doc_hash": None,
            "doc_loaded": False,
            "last_download_name": "document",
        }
    return sessions[sid]


def document_hash(text: str) -> str | None:
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def safe_filename(value: str, default: str = "document") -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", str(value).strip() or default)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return (stem or default)[:80]


def extract_text_from_file(uploaded_file) -> tuple[str, str | None]:
    filename = uploaded_file.filename.lower() if hasattr(uploaded_file, "filename") else ""
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    if filename.endswith(".pdf"):
        try:
            reader = pypdf.PdfReader(uploaded_file)
            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")
                except Exception:
                    return "", "Encrypted PDFs are not supported."
            pages = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text.strip())
            if not pages:
                return "", "No selectable text was found in this PDF."
            return "\n\n".join(pages), None
        except Exception as exc:
            return "", f"Could not read PDF: {exc}"

    if filename.endswith(".docx"):
        try:
            document = docx.Document(uploaded_file)
            parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))
            if not parts:
                return "", "No readable text was found in this DOCX."
            return "\n".join(parts), None
        except Exception as exc:
            return "", f"Could not read DOCX: {exc}"

    try:
        raw = uploaded_file.read()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return raw.decode(encoding), None
            except UnicodeDecodeError:
                continue
        return "", "Unsupported text encoding."
    except Exception as exc:
        return "", f"Could not read file: {exc}"


def create_word_doc(text: str) -> bytes:
    content = str(text or "No document content was generated.")
    document = docx.Document()
    styles = document.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(11)

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            document.add_paragraph()
        elif re.fullmatch(r"[═─\-]{4,}", line):
            continue
        elif line.startswith("# "):
            document.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            document.add_heading(line[3:].strip(), level=2)
        elif line.isupper() and len(line) <= 80 and any(ch.isalpha() for ch in line):
            document.add_heading(line.title(), level=2)
        elif line.startswith(("• ", "- ")):
            document.add_paragraph(line[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\.\s+", line):
            document.add_paragraph(re.sub(r"^\d+\.\s+", "", line), style="List Number")
        else:
            document.add_paragraph(line)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def create_pdf(text: str) -> bytes:
    content = str(text or "No document content was generated.")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    font_path = FONT_DIR / "ArialUnicode.ttf"
    font_name = "ArialUnicode" if font_path.exists() else "Helvetica"
    if font_path.exists():
        pdf.add_font(font_name, "", str(font_path), uni=True)
    pdf.set_font(font_name, "", 10)
    page_w = pdf.w - pdf.l_margin - pdf.r_margin

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
        elif re.fullmatch(r"[═─\-]{4,}", stripped):
            pdf.ln(2)
        elif stripped.isupper() and len(stripped) <= 80 and any(ch.isalpha() for ch in stripped):
            pdf.set_font(font_name, "", 13)
            pdf.cell(page_w, 8, stripped.title(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_name, "", 10)
        elif stripped.startswith(("• ", "- ")):
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(page_w - 5, 5, stripped[2:])
        elif re.match(r"^\d+\.\s+", stripped):
            pdf.set_x(pdf.l_margin + 5)
            pdf.multi_cell(page_w - 5, 5, re.sub(r"^\d+\.\s+", "", stripped))
        else:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(page_w, 5, stripped)

    return pdf.output()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    sid = data.get("session_id", request.remote_addr)
    user_input = data.get("message", "").strip()
    doc_text = data.get("document_text", "").strip()
    doc_filename = data.get("document_filename", DEFAULT_FILENAME)

    if not user_input:
        return jsonify({"error": "Message is required"}), 400

    sess = get_session(sid)
    current_hash = document_hash(doc_text) if doc_text else None
    if current_hash and sess["last_doc_hash"] != current_hash:
        sess["doc_loaded"] = False

    should_mark_doc = bool(doc_text and not sess["doc_loaded"])
    if should_mark_doc:
        task = f"[DOCUMENT: {doc_filename}]\n{doc_text}\n\nRequest: {user_input}"
    else:
        task = user_input

    sess["thinking"] = []

    def on_tool_call(tool_name, tool_input, tool_output):
        sess["thinking"].append({
            "tool": tool_name,
            "input": tool_input,
            "output": str(tool_output)[:300],
        })

    result = run_agent(
        task=task,
        config=DOCUMENT_AGENT_CONFIG,
        memory=sess["memory"],
        on_tool_call=on_tool_call,
    )

    answer = result.get("answer", "Sorry, I could not complete that request.")
    success = result.get("success", False)

    if should_mark_doc and success:
        sess["last_doc_hash"] = current_hash
        sess["doc_loaded"] = True
    sess["last_download_name"] = doc_filename if doc_text else "document_latest"

    return jsonify({
        "answer": answer,
        "thinking": sess["thinking"],
        "success": success,
        "session_id": sid,
    })


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    text, error = extract_text_from_file(file)
    if error:
        return jsonify({"error": error}), 422

    if len(text) > MAX_DOCUMENT_CHARS:
        text = text[:MAX_DOCUMENT_CHARS]

    return jsonify({
        "text": text,
        "filename": file.filename,
    })


@app.route("/api/download-docx", methods=["POST"])
def download_docx():
    data = request.get_json()
    text = data.get("text", "") if data else ""
    if not text:
        return jsonify({"error": "No content provided"}), 400

    docx_bytes = create_word_doc(text)
    filename = safe_filename(data.get("filename", ""), "document") + ".docx"

    return jsonify({
        "filename": filename,
        "content": docx_bytes.hex(),
    })


@app.route("/api/download-pdf", methods=["POST"])
def download_pdf():
    data = request.get_json()
    text = data.get("text", "") if data else ""
    if not text:
        return jsonify({"error": "No content provided"}), 400

    pdf_bytes = create_pdf(text)
    filename = safe_filename(data.get("filename", ""), "document") + ".pdf"

    return jsonify({
        "filename": filename,
        "content": pdf_bytes.hex(),
    })


DOC_SYSTEM_PROMPTS = {
    "resume": """You are a professional resume writer. Output ONLY valid JSON with this exact schema:
{
  "name": "Full Name",
  "contact": { "email": "...", "phone": "...", "location": "...", "linkedin": "...", "github": "..." },
  "summary": "2-3 sentence professional summary with **bold metrics**.",
  "experience": [{ "company": "", "role": "", "location": "", "dates": "", "bullets": ["Achievement **X%** ..."] }],
  "projects": [{ "name": "", "technologies": "", "dates": "", "bullets": ["..."] }],
  "education": [{ "institution": "", "degree": "", "location": "", "dates": "", "details": "" }],
  "skills": { "languages": "", "frameworks": "", "tools": "" }
}
RULES: **bold** for metrics. Achievement-oriented bullets. FAANG style. 1 page. ATS-friendly.""",

    "cover_letter": """You are a professional cover letter writer. Output ONLY valid JSON with this schema:
{
  "sender": { "name": "", "email": "", "phone": "", "address": "" },
  "recipient": { "name": "", "company": "", "address": "" },
  "date": "",
  "subject": "",
  "greeting": "",
  "body": ["Paragraph 1...", "Paragraph 2...", "Paragraph 3..."],
  "closing": "Sincerely,",
  "sender_title": ""
}
RULES: Professional tone. 3-4 paragraphs. Tailored to the role. Use **bold** for emphasis where appropriate.""",

    "proposal": """You are a business proposal writer. Output ONLY valid JSON with this schema:
{
  "title": "",
  "prepared_by": "",
  "prepared_for": "",
  "date": "",
  "executive_summary": "",
  "problem_statement": "",
  "solution": "",
  "scope": [{ "title": "", "description": "" }],
  "pricing": [{ "item": "", "cost": 0 }],
  "budget": "",
  "timeline": "",
  "deliverables": ["Deliverable 1", "Deliverable 2"]
}
RULES: Professional. Persuasive. Clear pricing. Use **bold** for key numbers.""",

    "report": """You are a professional report writer. Output ONLY valid JSON with this schema:
{
  "title": "",
  "prepared_by": "",
  "date": "",
  "abstract": "",
  "executive_summary": "",
  "introduction": "",
  "objectives": "",
  "methodology": "",
  "implementation": "",
  "analysis": "",
  "findings": "",
  "recommendations": "",
  "conclusion": "",
  "references": ["Reference 1", "Reference 2"]
}
RULES: Academic/professional tone. Use **bold** for key findings. Structured format.""",

    "invoice": """You are an invoice generator. Output ONLY valid JSON with this schema:
{
  "business": { "name": "", "email": "", "phone": "", "address": "" },
  "client": { "name": "", "company": "", "email": "", "address": "" },
  "invoice_number": "INV-001",
  "date": "",
  "due_date": "",
  "currency": "$",
  "items": [{ "description": "", "qty": 1, "rate": 0 }],
  "tax_rate": 0.18,
  "payment_method": "Bank Transfer",
  "notes": ""
}
RULES: Professional. Clean. Itemized. Calculate totals from qty * rate.""",

    "email": """You are a professional email writer. Output ONLY valid JSON with this schema:
{
  "to": "",
  "cc": "",
  "subject": "",
  "greeting": "Hi,",
  "body": ["Paragraph 1", "Paragraph 2"],
  "body_text": "",
  "closing": "Best regards,",
  "sender_name": "",
  "sender_title": "",
  "sender_email": ""
}
RULES: Use **bold** for emphasis. Tone varies by context (professional/friendly). Keep concise."""
}


@app.route("/api/generate-resume", methods=["POST"])
def generate_resume():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    prompt = data.get("prompt", "").strip()
    doc_type = data.get("doc_type", "resume")
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400

    system_prompt = DOC_SYSTEM_PROMPTS.get(doc_type, DOC_SYSTEM_PROMPTS["resume"])

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify({"error": "API key not configured"}), 500

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=data.get("model", "deepseek-chat"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4000,
        )
        content = response.choices[0].message.content or ""

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return jsonify({"error": "AI response was not valid JSON", "raw": content[:500]}), 422

        doc_data = json.loads(json_match.group())
        return jsonify({"resume": doc_data})

    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 500


@app.route("/api/generate-stream", methods=["POST"])
def generate_stream():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    prompt = data.get("prompt", "").strip()
    doc_type = data.get("doc_type", "resume")
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    system_prompt = DOC_SYSTEM_PROMPTS.get(doc_type, DOC_SYSTEM_PROMPTS["resume"])
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify({"error": "API key not configured"}), 500
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    client = OpenAI(api_key=api_key, base_url=base_url)
    def event_stream():
        try:
            response = client.chat.completions.create(
                model=data.get("model", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4000,
                stream=True,
            )
            full_text = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_text += token
                    yield f"data: {json.dumps({'t': token})}\n\n"
            json_match = re.search(r"\{.*\}", full_text, re.DOTALL)
            if json_match:
                yield f"data: {json.dumps({'d': json.loads(json_match.group())})}\n\n"
            else:
                yield f"data: {json.dumps({'e': 'Could not parse JSON from AI response', 'r': full_text[:500]})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'e': str(e)[:300]})}\n\n"
    resp = Response(stream_with_context(event_stream()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp

@app.route("/api/generate-html-docx", methods=["POST"])
def generate_html_docx():
    from bs4 import BeautifulSoup

    data = request.get_json()
    html_content = (data or {}).get("html", "")
    css_content = (data or {}).get("css", "")
    filename = safe_filename((data or {}).get("filename", ""), "resume") + ".docx"
    if not html_content.strip():
        return jsonify({"error": "No HTML provided"}), 400

    doc = docx.Document()

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    pf = style.paragraph_format
    pf.space_after = Pt(3)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.15

    def add_run(paragraph, text, bold=False, italic=False, underline=False, size=None, color=None, font_name=None):
        if not text.strip():
            return
        run = paragraph.add_run(text)
        if bold:
            run.bold = True
        if italic:
            run.italic = True
        if underline:
            run.underline = True
        if size:
            run.font.size = size
        if color:
            run.font.color.rgb = color
        if font_name:
            run.font.name = font_name
        return run

    def inline_run(paragraph, el):
        text = el.get_text() if hasattr(el, 'get_text') else str(el)
        if not text.strip():
            return
        tag = el.name if hasattr(el, 'name') else None
        is_bold = tag in ('strong', 'b', 'h1', 'h2', 'h3', 'h4', 'th')
        is_italic = tag in ('em', 'i')
        add_run(paragraph, text, bold=is_bold, italic=is_italic)

    def process_inline(paragraph, parent):
        for child in parent.children:
            if isinstance(child, str):
                add_run(paragraph, child)
            elif child.name in ('strong', 'b'):
                add_run(paragraph, child.get_text(), bold=True)
            elif child.name in ('em', 'i'):
                add_run(paragraph, child.get_text(), italic=True)
            elif child.name == 'br':
                add_run(paragraph, '\n')
            elif child.name == 'span':
                style_attr = child.get('style', '')
                bold = 'font-weight' in style_attr and ('bold' in style_attr or '700' in style_attr)
                add_run(paragraph, child.get_text(), bold=bold)
            elif child.name == 'a':
                add_run(paragraph, child.get_text(), underline=True)
            else:
                process_inline(paragraph, child)

    def has_text_content(el):
        text = el.get_text(strip=True)
        return bool(text)

    soup = BeautifulSoup(html_content, 'html.parser')

    body = soup.find('body')
    root = body if body else soup

    for el in root.find_all(recursive=False):
        if not has_text_content(el):
            continue
        tag = el.name if hasattr(el, 'name') else None
        if not tag or tag in ('script', 'style', 'nav', 'aside', 'meta', 'link'):
            continue

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if tag == 'h1' else WD_ALIGN_PARAGRAPH.LEFT
            level = int(tag[1])
            sizes = {1: Pt(20), 2: Pt(14), 3: Pt(12), 4: Pt(11)}
            size = sizes.get(level, Pt(11))
            text = el.get_text(strip=True)
            add_run(p, text, bold=True, size=size)
            p.paragraph_format.space_before = Pt(14 if level <= 2 else 10)
            p.paragraph_format.space_after = Pt(4 if level <= 2 else 3)

        elif tag == 'p':
            p = doc.add_paragraph()
            process_inline(p, el)
            if p.text.strip():
                p.paragraph_format.space_after = Pt(4)

        elif tag == 'div':
            cls = ' '.join(el.get('class', []))
            text = el.get_text(strip=True)
            if not text:
                continue

            is_section = any(c in cls for c in ['r-section', 'prop-section', 'rpt-section', 'inv-header',
                                                 'section-label', 'rpt-abstract-label', 'cl-subject',
                                                 'email-subject-line'])
            is_header = any(c in cls for c in ['r-exp-header', 'r-edu-header', 'email-header-bar',
                                                'prop-card-title', 'cl-sender', 'cl-name', 'cl-greeting',
                                                'cl-closing', 'inv-from', 'inv-company', 'inv-number',
                                                'prop-cover-page'])
            is_body = any(c in cls for c in ['cl-body', 'email-body-content', 'prop-section', 'rpt-section'])

            if is_section:
                p = doc.add_paragraph()
                add_run(p, text, bold=True, size=Pt(10))
                p.paragraph_format.space_before = Pt(10)
                p.paragraph_format.space_after = Pt(3)
            elif is_header:
                p = doc.add_paragraph()
                for child in el.children:
                    if isinstance(child, str):
                        add_run(p, child)
                    elif child.name in ('strong', 'b', 'span'):
                        is_b = child.name in ('strong', 'b') or ('font-weight' in (child.get('style','')) and 'bold' in child.get('style',''))
                        add_run(p, child.get_text(), bold=is_b)
                    else:
                        add_run(p, child.get_text())
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(2)
            elif is_body:
                for sub_el in el.find_all(['p', 'div'], recursive=False):
                    sub_text = sub_el.get_text(strip=True)
                    if sub_text:
                        p = doc.add_paragraph()
                        process_inline(p, sub_el)
                        p.paragraph_format.space_after = Pt(4)
            else:
                p = doc.add_paragraph()
                process_inline(p, el)
                p.paragraph_format.space_after = Pt(3)

        elif tag == 'ul':
            for li in el.find_all('li', recursive=False):
                text = li.get_text(strip=True)
                if text:
                    p = doc.add_paragraph(style='List Bullet')
                    process_inline(p, li)
                    p.paragraph_format.space_after = Pt(1)
                    p.paragraph_format.left_indent = Inches(0.3)

        elif tag == 'ol':
            for i, li in enumerate(el.find_all('li', recursive=False)):
                text = li.get_text(strip=True)
                if text:
                    p = doc.add_paragraph()
                    add_run(p, f"{i+1}. ", bold=True)
                    process_inline(p, li)
                    p.paragraph_format.space_after = Pt(1)
                    p.paragraph_format.left_indent = Inches(0.3)

        elif tag == 'hr':
            p = doc.add_paragraph()
            add_run(p, '─' * 65, size=Pt(6))
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)

        elif tag == 'blockquote':
            p = doc.add_paragraph()
            process_inline(p, el)
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.right_indent = Inches(0.2)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)

        elif tag == 'table':
            for tr in el.find_all('tr'):
                cells = tr.find_all(['td', 'th'])
                if cells:
                    row_text = ' | '.join(c.get_text(strip=True) for c in cells)
                    p = doc.add_paragraph()
                    add_run(p, row_text, size=Pt(9.5))
                    p.paragraph_format.space_after = Pt(2)

        else:
            text = el.get_text(strip=True)
            if text:
                p = doc.add_paragraph()
                process_inline(p, el)
                p.paragraph_format.space_after = Pt(3)

    buffer = io.BytesIO()
    doc.save(buffer)
    return jsonify({"filename": filename, "content": buffer.getvalue().hex()})


@app.route("/api/new-session", methods=["POST"])
def new_session():
    sid = str(uuid.uuid4())
    sessions[sid] = {
        "memory": Memory(),
        "thinking": [],
        "last_doc_hash": None,
        "doc_loaded": False,
        "last_download_name": "document",
    }
    return jsonify({"session_id": sid})


@socketio.on("connect")
def handle_connect():
    emit("session_id", {"session_id": request.sid})


@socketio.on("send_message")
def handle_socket_message(data):
    sid = request.sid
    user_input = data.get("message", "").strip()
    doc_text = data.get("document_text", "").strip()
    doc_filename = data.get("document_filename", DEFAULT_FILENAME)

    if not user_input:
        return

    sess = get_session(sid)
    current_hash = document_hash(doc_text) if doc_text else None
    if current_hash and sess["last_doc_hash"] != current_hash:
        sess["doc_loaded"] = False

    should_mark_doc = bool(doc_text and not sess["doc_loaded"])
    task = f"[DOCUMENT: {doc_filename}]\n{doc_text}\n\nRequest: {user_input}" if should_mark_doc else user_input

    sess["thinking"] = []

    def on_tool_call(tool_name, tool_input, tool_output):
        emit("thinking_step", {
            "tool": tool_name,
            "input": tool_input,
            "output": str(tool_output)[:300],
        })

    result = run_agent(
        task=task,
        config=DOCUMENT_AGENT_CONFIG,
        memory=sess["memory"],
        on_tool_call=on_tool_call,
    )

    answer = result.get("answer", "Sorry, I could not complete that request.")
    success = result.get("success", False)

    if should_mark_doc and success:
        sess["last_doc_hash"] = current_hash
        sess["doc_loaded"] = True
    sess["last_download_name"] = doc_filename if doc_text else "document_latest"

    emit("agent_response", {
        "answer": answer,
        "thinking": sess["thinking"],
        "success": success,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
