# DocAgent — Universal AI Document Platform

A full-stack AI-powered document creation and editing platform. Generate, edit, and export any professional document using AI — from resumes and proposals to NDAs, technical documentation, marketing plans, and more.

## Features

- **Universal Document Generation** — Type any document request and AI generates it with proper professional structure
- **Template Shortcuts** — Quick-access cards for common types: Resume, Cover Letter, Proposal, Report, Invoice, Email, Documentation
- **Rich WYSIWYG Editor** — Full floating toolbar with formatting, fonts, colors, lists, tables, images, links
- **File Upload** — Upload PDF, DOCX, or TXT files for AI analysis, summarization, and Q&A
- **Export** — Download as PDF, DOCX, HTML, or copy as text/HTML
- **Streaming Generation** — Real-time token-by-token streaming with progressive rendering
- **Agent Chat** — Conversational AI agent that creates, edits, improves, and analyzes documents
- **Session Management** — Persistent conversation history per session

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Abbaskay/docs_agent.git
cd docs_agent

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and set your DEEPSEEK_API_KEY

# Run the app
python run.py
```

Open http://localhost:5000 in your browser.

## Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | DeepSeek API key **(required)** |
| `PORT` | 5000 | Server port |
| `DATABASE_URL` | sqlite:///aidoc.db | Database URL (SQLite/PostgreSQL) |
| `REDIS_URL` | — | Redis URL (optional, falls back to in-memory) |
| `API_KEY` | — | API key for authenticated rate limits |
| `MAX_UPLOAD_SIZE_MB` | 20 | Max upload file size |

See `.env.example` for the full list of options.

## Architecture

```
├── app.py                  # Flask routes, streaming, WebSocket, file handling
├── config.py               # Agent configuration + auto-registration
├── prompt.py               # System prompt for the AI agent
├── document_tools.py       # 10 document tools (generate, edit, analyze, export)
├── core/
│   ├── runner.py           # Agent orchestration loop (LLM + tool execution)
│   ├── memory.py           # Conversation history management
│   ├── database.py         # SQLAlchemy models (Generation, Export, Upload, ApiUsage)
│   ├── cache.py            # Redis + in-memory caching
│   ├── rate_limiter.py     # Per-session rate limiting with burst protection
│   ├── security.py         # Input sanitization, prompt injection detection, file validation
│   ├── logger.py           # Structured JSONL logging
│   └── exceptions.py       # Error hierarchy (Validation, RateLimit, AI, Export)
├── registries/             # Central registries for tools, schemas, and prompts
├── tools/
│   ├── general_tools.py    # search_web, calculate, get_current_time
│   └── hyperzod_tools.py   # Order management tools
├── static/
│   ├── css/style.css       # Dark-themed responsive stylesheet
│   └── js/app.js           # Client-side SPA with classifier, renderers, editor
├── templates/
│   └── index.html          # Single-page application
└── fonts/
    └── ArialUnicode.ttf    # Unicode font for PDF generation
```

## Document Classification

DocAgent uses a weighted intent classifier to detect the document type from user input. It supports:

- **7 specific types**: Resume, Cover Letter, Proposal, Report, Invoice, Email, Documentation
- **Universal catch-all**: Legal (NDAs, contracts), business plans, marketing, academic, technical docs, and any custom document type
- **Confidence threshold**: High-confidence matches route to specific templates; everything else uses the universal generator
- **Never defaults to Resume** — unknown types route to the generic document generator

## Document Generators

| Type | System Prompt | Renderer |
|---|---|---|
| Resume / CV | Structured JSON schema | renderResume |
| Cover Letter | Structured JSON schema | renderCoverLetter |
| Business Proposal | Structured JSON schema | renderProposal |
| Project Report | Structured JSON schema | renderReport |
| Invoice | Structured JSON schema | renderInvoice |
| Email Template | Structured JSON schema | renderEmail |
| Documentation | Technical writing prompt | renderDocumentation |
| Anything else | Universal adaptive prompt | renderGeneric |

## Tech Stack

- **Backend**: Python, Flask, Flask-SocketIO, SQLAlchemy
- **Frontend**: Vanilla JS, contenteditable, CSS custom properties
- **AI**: DeepSeek Chat (OpenAI-compatible API)
- **PDF**: fpdf2, html2pdf.js
- **DOCX**: python-docx
- **Database**: SQLite (default) / PostgreSQL
