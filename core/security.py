import os
import re
import unicodedata

try:
    import bleach

    HAS_BLEACH = True
except ImportError:
    HAS_BLEACH = False

MAX_PROMPT_LENGTH = 100000
MAX_DOCUMENT_LENGTH = 100_000
MAX_FILENAME_LENGTH = 200
MAX_TITLE_LENGTH = 200

HTML_TAG_RE = re.compile(r"<[^>]*>")
SCRIPT_RE = re.compile(
    r"(<script[^>]*>.*?</script>|javascript\s*:|on\w+\s*=)",
    re.IGNORECASE | re.DOTALL,
)
PROMPT_INJECTION_PATTERNS = [
    r"(?i)(?:(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+)?(?:previous|above|system|instructions|prompt))",
    r"(?i)(?:pretend\s+(?:to\s+)?be|act\s+as\s+(?:if\s+)?you)",
    r"(?i)(?:new\s+(?:system\s+)?prompt|updated\s+instructions)",
    r"(?i)(?:you\s+are\s+(?:now\s+)?(?:an?\s+)?(?:free|unrestricted|unbounded|ungoverned))",
    r"(?i)(?:output\s+(?:your\s+)?(?:system\s+)?prompt|show\s+(?:your\s+)?(?:system\s+)?instructions)",
    r"(?i)(?:you\s+(?:will|must|shall)\s+(?:now\s+)?ignore)",
    r"(?i)(?:do\s+(?:not\s+)?(?:follow|obey|adhere)\s+(?:your\s+)?(?:previous|above))",
    r"(?i)(?:repeat\s+(?:after\s+(?:me|us)|(?:the\s+)?(?:above|previous)))",
    r"(?i)(?:let\s+(?:me\s+)?(?:take\s+over|control|change))",
    (r"(?i)(?:"
     r"system\s+prompt|"
     r"instructions?\s+above|"
     r"role\s+play|"
     r"dangerous|"
     r"harmful\s+content"
     r")"),
]
INJECTION_THRESHOLD = 3

MAGIC_BYTES: dict[str, bytes] = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
}

FILE_EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024
DANGEROUS_FILENAME_PATTERN = re.compile(r"[\\/:*?\"<>|~]")
PATH_TRAVERSAL_PATTERN = re.compile(r"(?:\.\./|\.\.\\|~/)")
NULL_BYTE = re.compile(r"\x00")


def sanitize_text(text: str | None, max_length: int = 5000) -> str:
    if not text:
        return ""
    raw = str(text)
    raw = NULL_BYTE.sub("", raw)
    if HAS_BLEACH:
        raw = bleach.clean(raw, tags=[], strip=True)
    else:
        raw = strip_html_tags(raw)
    raw = unicodedata.normalize("NFKC", raw)
    raw = raw.strip()
    if len(raw) > max_length:
        raw = raw[:max_length]
    return raw


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "unnamed"
    raw = str(filename).strip()
    raw = NULL_BYTE.sub("", raw)
    raw = PATH_TRAVERSAL_PATTERN.sub("", raw)
    raw = DANGEROUS_FILENAME_PATTERN.sub("_", raw)
    raw = re.sub(r"[^\w.\- ]", "", raw)
    raw = raw.strip(". ")
    if not raw:
        return "unnamed"
    if len(raw) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(raw)
        ext = ext[:10]
        max_name_len = MAX_FILENAME_LENGTH - len(ext) - 1
        if max_name_len > 0:
            name = name[:max_name_len]
        raw = name + ext
    return raw


def sanitize_html_content(text: str | None) -> str:
    if not text:
        return ""
    raw = str(text)
    raw = SCRIPT_RE.sub("", raw)
    if HAS_BLEACH:
        raw = bleach.clean(raw, tags=[], strip=True)
    else:
        raw = strip_html_tags(raw)
    raw = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    raw = raw.replace('"', "&quot;").replace("'", "&#x27;")
    return raw


def validate_prompt(prompt: str | None, max_length: int = MAX_PROMPT_LENGTH) -> str:
    if not prompt:
        raise ValueError("Prompt is required.")
    raw = str(prompt).strip()
    if not raw:
        raise ValueError("Prompt cannot be empty.")
    if len(raw) < 2:
        raise ValueError("Prompt is too short.")
    if len(raw) > max_length:
        raise ValueError(f"Prompt exceeds maximum length of {max_length} characters.")
    if not raw.isprintable() and not any(c.isalpha() for c in raw):
        raise ValueError("Prompt contains non-printable characters.")
    score = 0
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, raw):
            score += 1
    if score >= INJECTION_THRESHOLD:
        raise ValueError("Prompt detected as potential injection attempt.")
    return raw


def validate_document_text(text: str | None, max_length: int = MAX_DOCUMENT_LENGTH) -> str:
    if not text:
        return ""
    raw = str(text)
    if len(raw) > max_length:
        raw = raw[:max_length]
    if not raw.isprintable() and not any(c.isalpha() for c in raw):
        raise ValueError("Document contains non-printable content.")
    return raw


def verify_file_extension(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def verify_file_signature(data: bytes, filename: str) -> bool:
    if not data or not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".txt":
        try:
            data.decode("utf-8-sig")
            return True
        except (UnicodeDecodeError, ValueError):
            try:
                data.decode("latin-1")
                for byte in data:
                    if byte == 0:
                        return False
                return True
            except Exception:
                return False
    expected_magic = MAGIC_BYTES.get(ext)
    if expected_magic:
        return data[: len(expected_magic)] == expected_magic
    return False


def verify_mime_type(mime: str | None, filename: str) -> bool:
    if not mime:
        return verify_file_extension(filename)
    ext = os.path.splitext(filename)[1].lower()
    expected = FILE_EXTENSION_TO_MIME.get(ext)
    if not expected:
        return False
    return mime.lower() == expected or mime.lower().startswith(expected)


def validate_upload(file_data: bytes, filename: str, content_type: str | None = None) -> None:
    if not file_data:
        raise ValueError("No file data provided.")
    if len(file_data) > MAX_UPLOAD_SIZE:
        raise ValueError(f"File exceeds maximum size of {MAX_UPLOAD_SIZE // (1024*1024)}MB.")
    if not verify_file_extension(filename):
        raise ValueError(
            f"File extension '{os.path.splitext(filename)[1]}' not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    if not verify_file_signature(file_data, filename):
        raise ValueError(
            f"File content does not match expected format for '{os.path.splitext(filename)[1]}'."
        )


def sanitize_export_filename(filename: str, default: str = "document") -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{1,8}$", "", str(filename).strip() or default)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return (stem or default)[:80]


def strip_html_tags(text: str) -> str:
    return HTML_TAG_RE.sub("", text)
