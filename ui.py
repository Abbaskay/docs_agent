"""
document_agent/ui.py — Full standalone Streamlit UI for the Document Agent.

Provides chat interface, template quick-pick buttons, document paste input,
thinking drawer, dark/light theme, and export button.

Run via:
    streamlit run document_agent/run.py
"""

import streamlit as st
import docx
import pypdf

# Import triggers __init__.py → config.py → register()
from config import DOCUMENT_AGENT_CONFIG
from core.runner import run_agent
from core.memory import Memory

def extract_text_from_file(uploaded_file) -> str:
    """Extracts text from an uploaded PDF, DOCX, or TXT file."""
    if uploaded_file.name.lower().endswith(".pdf"):
        try:
            reader = pypdf.PdfReader(uploaded_file)
            return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        except Exception as e:
            return f"Error reading PDF: {str(e)}"
    elif uploaded_file.name.lower().endswith(".docx"):
        try:
            doc = docx.Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            return f"Error reading DOCX: {str(e)}"
    else:
        try:
            return uploaded_file.getvalue().decode("utf-8")
        except Exception as e:
            return f"Error reading file: {str(e)}"

def create_word_doc(text: str) -> str:
    """Wraps text in a basic HTML structure that MS Word reads natively."""
    escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8"><title>Document</title></head>
<body style="font-family: 'Courier New', Courier, monospace; font-size: 11pt; white-space: pre-wrap;">
{escaped_text}
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Document Agent — Hyperzod",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Theme detection
# ─────────────────────────────────────────────────────────────────────────────

if "theme" not in st.session_state:
    st.session_state.theme = st.query_params.get("theme", "light")

theme = st.session_state.theme
is_dark = theme == "dark"

# ─────────────────────────────────────────────────────────────────────────────
# CSS injection
# ─────────────────────────────────────────────────────────────────────────────

if is_dark:
    bg_main   = "#0f1117"
    bg_card   = "#1a1d27"
    bg_bubble_user = "#2563eb"
    bg_bubble_ai   = "#1e2130"
    text_main = "#e8eaf0"
    text_sub  = "#8b95a8"
    accent    = "#4f8ef7"
    border    = "#2a2f3e"
    input_bg  = "#1a1d27"
    btn_bg    = "#1e2130"
    btn_hover = "#2563eb"
else:
    bg_main   = "#f8f9fc"
    bg_card   = "#ffffff"
    bg_bubble_user = "#2563eb"
    bg_bubble_ai   = "#f0f2f8"
    text_main = "#1a1d27"
    text_sub  = "#6b7280"
    accent    = "#2563eb"
    border    = "#e2e6f0"
    input_bg  = "#ffffff"
    btn_bg    = "#f0f2f8"
    btn_hover = "#2563eb"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset & Base ── */
*, *::before, *::after {{ box-sizing: border-box; }}

html, body, [data-testid="stAppViewContainer"] {{
    background: {bg_main} !important;
    color: {text_main} !important;
    font-family: 'Inter', sans-serif !important;
}}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="collapsedControl"],
button[kind="header"] {{ display: none !important; }}

section[data-testid="stSidebar"] {{ display: none !important; }}

/* ── Main container ── */
[data-testid="stAppViewContainer"] > .main {{
    background: {bg_main} !important;
    padding-bottom: 100px;
}}

.block-container {{
    max-width: 780px;
    padding: 1.5rem 1.5rem 6rem !important;
}}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {{
    background: transparent !important;
    padding: 4px 0 !important;
}}

[data-testid="stChatMessageContent"] {{
    background: {bg_bubble_ai} !important;
    border-radius: 16px !important;
    padding: 14px 18px !important;
    font-size: 15px !important;
    line-height: 1.65 !important;
    border: 1px solid {border} !important;
    color: {text_main} !important;
}}

[data-testid="stChatMessage"][data-testid*="user"] [data-testid="stChatMessageContent"],
.stChatMessage:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {{
    background: {bg_bubble_user} !important;
    color: #ffffff !important;
    border: none !important;
}}

/* ── Chat input ── */
[data-testid="stChatInput"] {{
    background: {bg_card} !important;
    border: 1.5px solid {border} !important;
    border-radius: 14px !important;
    padding: 4px 8px !important;
}}

[data-testid="stChatInput"] textarea {{
    font-size: 16px !important;
    font-family: 'Inter', sans-serif !important;
    color: {text_main} !important;
    background: transparent !important;
    min-height: 44px !important;
}}

/* ── Quick-pick buttons ── */
.stButton > button {{
    width: 100% !important;
    min-height: 44px !important;
    background: {btn_bg} !important;
    color: {text_main} !important;
    border: 1.5px solid {border} !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.18s ease !important;
    cursor: pointer !important;
    padding: 0.45rem 0.75rem !important;
}}

.stButton > button:hover {{
    background: {btn_hover} !important;
    color: #ffffff !important;
    border-color: {btn_hover} !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.25) !important;
}}

/* ── Expander (thinking drawer + doc paste) ── */
[data-testid="stExpander"] {{
    background: {bg_card} !important;
    border: 1px solid {border} !important;
    border-radius: 12px !important;
    margin: 0.5rem 0 !important;
}}

[data-testid="stExpander"] summary {{
    font-size: 14px !important;
    font-weight: 500 !important;
    color: {text_sub} !important;
    padding: 10px 14px !important;
}}

/* ── Text inputs inside expander ── */
.stTextArea textarea, .stTextInput input {{
    font-size: 15px !important;
    font-family: 'Inter', sans-serif !important;
    background: {input_bg} !important;
    color: {text_main} !important;
    border: 1px solid {border} !important;
    border-radius: 8px !important;
    min-height: 44px !important;
}}

/* ── Spinner ── */
[data-testid="stSpinner"] {{
    color: {accent} !important;
}}

/* ── Caption / small text ── */
.stCaption, small {{
    color: {text_sub} !important;
    font-size: 12px !important;
}}

/* ── Divider ── */
hr {{
    border-color: {border} !important;
    margin: 0.75rem 0 !important;
}}

/* ── Header area ── */
.doc-agent-header {{
    text-align: center;
    padding: 1.5rem 0 1rem;
}}

.doc-agent-header .emoji {{
    font-size: 3rem;
    line-height: 1;
    margin-bottom: 0.5rem;
}}

.doc-agent-header h1 {{
    font-size: 2rem;
    font-weight: 700;
    color: {accent};
    margin: 0.25rem 0;
    letter-spacing: -0.5px;
}}

.doc-agent-header p {{
    color: {text_sub};
    font-size: 0.95rem;
    margin: 0;
}}

/* ── Section labels ── */
.section-label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {text_sub};
    margin: 1rem 0 0.4rem;
}}

/* ── Theme toggle ── */
.theme-row {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 0;
}}

/* ── Code blocks inside chat ── */
code {{
    background: {bg_main} !important;
    color: {accent} !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    font-size: 13px !important;
}}

pre code {{
    background: transparent !important;
    padding: 0 !important;
    font-size: 13px !important;
    line-height: 1.6 !important;
    white-space: pre-wrap !important;
    word-break: break-word !important;
}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialization
# ─────────────────────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []
if "memory" not in st.session_state:
    st.session_state.memory = Memory()
if "thinking" not in st.session_state:
    st.session_state.thinking = []
if "quick_pick" not in st.session_state:
    st.session_state.quick_pick = None
if "doc_injected" not in st.session_state:
    st.session_state.doc_injected = False

# ─────────────────────────────────────────────────────────────────────────────
# Theme toggle (top-right)
# ─────────────────────────────────────────────────────────────────────────────

toggle_col1, toggle_col2 = st.columns([8, 1])
with toggle_col2:
    toggle_icon = "☀️" if is_dark else "🌙"
    if st.button(toggle_icon, key="theme_toggle", help="Toggle dark/light mode"):
        st.session_state.theme = "light" if is_dark else "dark"
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="doc-agent-header">
  <div class="emoji">📄</div>
  <h1>Document Agent</h1>
  <p>Create, analyze, and improve professional documents</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Template quick-pick grid
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Quick Templates</div>', unsafe_allow_html=True)

quick_pick_map = {
    "📋 CV / Resume":    "I need to create a professional CV / Resume",
    "✉️ Cover Letter":   "Help me write a cover letter",
    "📊 Proposal":       "I need a business proposal template",
    "📁 Report":         "Create a project report for me",
    "🧾 Invoice":        "Generate a professional invoice",
    "📧 Email":          "I need an email template",
}

col1, col2, col3 = st.columns(3)
btn_items = list(quick_pick_map.items())

for idx, (label, message) in enumerate(btn_items):
    col = [col1, col2, col3][idx % 3]
    with col:
        if st.button(label, key=f"qp_{idx}"):
            st.session_state.messages.append({"role": "user", "content": message})
            st.session_state.quick_pick = label
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Document paste expander
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Existing Document</div>', unsafe_allow_html=True)

with st.expander("📎 Upload or Paste existing document", expanded=False):
    uploaded_file = st.file_uploader("Upload PDF, Word, or Text Document", type=["pdf", "docx", "txt"])
    
    doc_content = st.text_area(
        "Or paste document content here",
        height=160,
        key="doc_content",
        placeholder="Paste any document, article, report, or text...",
        label_visibility="collapsed",
    )
    doc_filename = st.text_input(
        "Document name (optional)",
        value="my_document.txt",
        key="doc_filename",
    )
    st.caption("The agent will analyze this content when you send a message below.")

# ─────────────────────────────────────────────────────────────────────────────
# Chat history rendering
# ─────────────────────────────────────────────────────────────────────────────

# Welcome message when chat is empty
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown("""
👋 Hi! I'm your **Document Agent**.

I can help you:
- 📋 Create a **CV, Cover Letter, Proposal, Report, Invoice, or Email** template
- 📄 **Summarize** any document you paste
- ❓ **Answer questions** from your document
- ✏️ **Edit and improve** any content
- 📤 **Export** documents as clean markdown

Pick a template above or type what you need below.
""")
else:
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
        # Action buttons after each assistant message (except the last pending one)
        if msg["role"] == "assistant" and st.session_state.thinking:
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("📤 Export as Markdown", key=f"export_btn_{i}"):
                    export_req = "Export the last document as markdown"
                    st.session_state.messages.append({"role": "user", "content": export_req})
                    st.rerun()
            with col2:
                st.download_button(
                    label="💾 Download Word Doc",
                    data=create_word_doc(msg["content"]),
                    file_name=f"document_{i}.doc",
                    mime="application/msword",
                    key=f"download_btn_{i}"
                )

# ─────────────────────────────────────────────────────────────────────────────
# Thinking drawer
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.thinking:
    with st.expander(
        f"🧠 Agent thinking — {len(st.session_state.thinking)} step(s)",
        expanded=False,
    ):
        for step in st.session_state.thinking:
            st.markdown(f"**🔧 {step['tool']}**")
            st.code(str(step["input"]), language="python")
            st.markdown(f"*{str(step['output'])[:300]}{'...' if len(str(step['output'])) > 300 else ''}*")
            st.divider()
        if st.button("🗑️ Clear log", key="clear_thinking"):
            st.session_state.thinking = []
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Chat input + agent loop
# ─────────────────────────────────────────────────────────────────────────────

user_input = st.chat_input("What document do you need?")

if user_input:
    # Build the message to send to agent
    doc_text = st.session_state.get("doc_content", "").strip()
    filename  = st.session_state.get("doc_filename", "my_document.txt").strip()

    # Extract text from uploaded file if present
    if uploaded_file is not None:
        with st.spinner("Extracting text from file..."):
            extracted = extract_text_from_file(uploaded_file)
            if not extracted.strip() or extracted.startswith("Error"):
                st.warning(f"⚠️ Could not extract readable text from {uploaded_file.name}. It might be a scanned image or empty.")
            else:
                # Combine uploaded text with pasted text if both exist
                doc_text = f"{extracted}\n\n{doc_text}".strip()
                # Override the filename with the uploaded file's name
                if filename == "my_document.txt":
                    filename = uploaded_file.name

    current_doc_hash = hash(doc_text) if doc_text else None

    if doc_text and st.session_state.get("last_doc_hash") != current_doc_hash:
        final_input = (
            f"[DOCUMENT: {filename}]\n"
            f"{doc_text}\n\n"
            f"Request: {user_input}"
        )
        st.session_state.last_doc_hash = current_doc_hash
    else:
        final_input = user_input

    # Show user message (original, not injected version)
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Tool call callback for thinking drawer
    def on_tool_call(tool_name, tool_input, tool_output):
        """Record each tool call into the thinking log."""
        st.session_state.thinking.append({
            "tool":   tool_name,
            "input":  tool_input,
            "output": tool_output,
        })

    # Run the agent
    with st.chat_message("assistant"):
        with st.spinner("Creating your document..."):
            result = run_agent(
                task=final_input,
                config=DOCUMENT_AGENT_CONFIG,
                memory=st.session_state.memory,
                on_tool_call=on_tool_call,
            )
            answer = result.get("answer", "Sorry, I could not complete that request.")

        st.markdown(answer)

        # Action buttons immediately after response
        if st.session_state.thinking:
            col1, col2 = st.columns([1, 1])
            with col1:
                export_key = f"export_inline_{len(st.session_state.messages)}"
                if st.button("📤 Export as Markdown", key=export_key):
                    export_req = "Export the last document as markdown"
                    st.session_state.messages.append({"role": "user", "content": export_req})
                    st.rerun()
            with col2:
                download_key = f"download_inline_{len(st.session_state.messages)}"
                st.download_button(
                    label="💾 Download Word Doc",
                    data=create_word_doc(answer),
                    file_name="document_latest.doc",
                    mime="application/msword",
                    key=download_key
                )

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
