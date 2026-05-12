"""
document_agent/config.py — AgentConfig + self-registration for Document Agent.

Imports all tools and schemas, then calls register() to inject everything
into the shared framework registries. Called automatically on import via
document_agent/__init__.py.
"""

from core.config import AgentConfig
from prompt import DOCUMENT_AGENT_PROMPT
from document_tools import (
    generate_cv,
    generate_cover_letter,
    generate_proposal,
    generate_report,
    generate_invoice,
    generate_email,
    load_and_summarize,
    answer_from_document,
    edit_and_improve,
    export_as_markdown,
)
from registries.tool_registry import TOOL_REGISTRY
from registries.schema_registry import SCHEMA_REGISTRY
from registries.prompt_registry import PROMPT_REGISTRY

_registered = False


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------

DOCUMENT_AGENT_CONFIG = AgentConfig(
    name="document_agent",
    prompt_key="document_agent",
    tool_names=[
        "generate_cv",
        "generate_cover_letter",
        "generate_proposal",
        "generate_report",
        "generate_invoice",
        "generate_email",
        "load_and_summarize",
        "answer_from_document",
        "edit_and_improve",
        "export_as_markdown",
    ],
    max_tokens=4096,
    max_iterations=12,
    description="Create CV, proposals, invoices, emails. Analyze and improve documents.",
)


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic / OpenAI function-calling format)
# ---------------------------------------------------------------------------

_DOCUMENT_AGENT_SCHEMAS: dict[str, dict] = {
    "generate_cv": {
        "type": "function",
        "function": {
            "name": "generate_cv",
            "description": (
                "Generate a fully formatted professional CV / Resume. "
                "Use this when the user wants to create a CV or resume. "
                "Required fields: full_name, email, phone, location, job_title. "
                "All other fields are optional and will use placeholder text if omitted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":   {"type": "string", "description": "Candidate's full name."},
                    "email":       {"type": "string", "description": "Candidate's email address."},
                    "phone":       {"type": "string", "description": "Candidate's phone number."},
                    "location":    {"type": "string", "description": "Candidate's city and country."},
                    "job_title":   {"type": "string", "description": "Target job title or current role."},
                    "summary":     {"type": "string", "description": "Professional summary paragraph."},
                    "experience":  {"type": "string", "description": "Work experience block (multi-line text)."},
                    "education":   {"type": "string", "description": "Education block (multi-line text)."},
                    "skills":      {"type": "string", "description": "Comma-separated list of skills."},
                    "languages":   {"type": "string", "description": "Languages and proficiency levels."},
                },
                "required": ["full_name", "email", "phone", "location", "job_title"],
            },
        },
    },

    "generate_cover_letter": {
        "type": "function",
        "function": {
            "name": "generate_cover_letter",
            "description": (
                "Generate a professional cover letter for a job application. "
                "Use this when the user wants to apply for a job. "
                "Required: full_name, email, phone, job_title, company_name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name":        {"type": "string", "description": "Applicant's full name."},
                    "email":            {"type": "string", "description": "Applicant's email address."},
                    "phone":            {"type": "string", "description": "Applicant's phone number."},
                    "job_title":        {"type": "string", "description": "Position being applied for."},
                    "company_name":     {"type": "string", "description": "Name of the target company."},
                    "hiring_manager":   {"type": "string", "description": "Hiring manager's name or 'Hiring Manager'."},
                    "key_skills":       {"type": "string", "description": "Key skills to highlight."},
                    "why_company":      {"type": "string", "description": "Reason for interest in the company."},
                    "years_experience": {"type": "string", "description": "Years of relevant experience."},
                },
                "required": ["full_name", "email", "phone", "job_title", "company_name"],
            },
        },
    },

    "generate_proposal": {
        "type": "function",
        "function": {
            "name": "generate_proposal",
            "description": (
                "Generate a professional business proposal document. "
                "Use when the user needs to pitch a project or service. "
                "Required: project_title, prepared_by, prepared_for."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "project_title":      {"type": "string", "description": "Title of the project or proposal."},
                    "prepared_by":        {"type": "string", "description": "Name of the submitting person or company."},
                    "prepared_for":       {"type": "string", "description": "Name of the client or recipient."},
                    "problem_statement":  {"type": "string", "description": "Description of the problem being solved."},
                    "proposed_solution":  {"type": "string", "description": "Description of the proposed approach."},
                    "timeline":           {"type": "string", "description": "Project phases and schedule."},
                    "budget":             {"type": "string", "description": "Itemized cost breakdown."},
                    "deliverables":       {"type": "string", "description": "List of expected deliverables."},
                },
                "required": ["project_title", "prepared_by", "prepared_for"],
            },
        },
    },

    "generate_report": {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "Generate a structured project report with standard sections. "
                "Use when the user needs a formal project report or status report. "
                "Required: report_title, prepared_by."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "report_title":      {"type": "string", "description": "Title of the report."},
                    "prepared_by":       {"type": "string", "description": "Author's name."},
                    "project_name":      {"type": "string", "description": "Associated project name."},
                    "executive_summary": {"type": "string", "description": "High-level summary for stakeholders."},
                    "objectives":        {"type": "string", "description": "Goals and objectives of the project."},
                    "methodology":       {"type": "string", "description": "Approach and methods used."},
                    "findings":          {"type": "string", "description": "Key results and observations."},
                    "recommendations":   {"type": "string", "description": "Suggested next steps or actions."},
                    "conclusion":        {"type": "string", "description": "Closing remarks and summary."},
                },
                "required": ["report_title", "prepared_by"],
            },
        },
    },

    "generate_invoice": {
        "type": "function",
        "function": {
            "name": "generate_invoice",
            "description": (
                "Generate a professional invoice with automatic subtotal, 18% GST, "
                "and total calculation. Items should be provided as 'Name | qty | unit_price' "
                "per line. Required: business_name, business_email, client_name, client_email, items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "business_name":  {"type": "string", "description": "Name of the issuing business."},
                    "business_email": {"type": "string", "description": "Business contact email."},
                    "client_name":    {"type": "string", "description": "Client or customer name."},
                    "client_email":   {"type": "string", "description": "Client email address."},
                    "items":          {"type": "string", "description": "Line items in format 'Item name | quantity | unit price', one item per line, separated by newlines. Currency symbols are allowed in unit price."},
                    "due_date":       {"type": "string", "description": "Payment due date as display text, for example '30 June 2026'. Leave empty for 30 days from today."},
                    "payment_method": {"type": "string", "description": "Accepted payment method as display text, for example 'Bank Transfer' or 'UPI'."},
                    "notes":          {"type": "string", "description": "Additional notes for the client."},
                },
                "required": ["business_name", "business_email", "client_name", "client_email", "items"],
            },
        },
    },

    "generate_email": {
        "type": "function",
        "function": {
            "name": "generate_email",
            "description": (
                "Generate a professional email template. "
                "email_type options: follow_up, job_application, thank_you, "
                "meeting_request, project_update, apology, cold_outreach. "
                "tone options: professional, friendly, formal. "
                "Required: email_type, sender_name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email_type":     {"type": "string", "description": "One of: follow_up, job_application, thank_you, meeting_request, project_update, apology, cold_outreach."},
                    "sender_name":    {"type": "string", "description": "Name of the email sender."},
                    "recipient_name": {"type": "string", "description": "Name or title of the recipient."},
                    "subject":        {"type": "string", "description": "Email subject line (auto-generated if empty)."},
                    "context":        {"type": "string", "description": "Additional context to customize the body."},
                    "tone":           {"type": "string", "description": "One of: professional, friendly, formal."},
                },
                "required": ["email_type", "sender_name"],
            },
        },
    },

    "load_and_summarize": {
        "type": "function",
        "function": {
            "name": "load_and_summarize",
            "description": (
                "Load a document into memory and return a structured summary with statistics. "
                "Call this first whenever the user pastes document content. "
                "detail_level options: brief, medium, detailed. Required: content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content":      {"type": "string", "description": "The full text content of the document."},
                    "filename":     {"type": "string", "description": "Display name for the document."},
                    "detail_level": {"type": "string", "description": "One of: brief, medium, detailed."},
                },
                "required": ["content"],
            },
        },
    },

    "answer_from_document": {
        "type": "function",
        "function": {
            "name": "answer_from_document",
            "description": (
                "Answer a question using only the currently loaded document. "
                "Uses keyword-based sentence matching. "
                "A document must be loaded first via load_and_summarize. Required: question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to answer from the document."},
                },
                "required": ["question"],
            },
        },
    },

    "edit_and_improve": {
        "type": "function",
        "function": {
            "name": "edit_and_improve",
            "description": (
                "Edit and improve the provided content or the last generated document. "
                "improvement_type options: general, formal, concise, professional, grammar. "
                "All parameters are optional — will use last generated document if content is empty."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content":          {"type": "string", "description": "Text to improve (uses last document if empty)."},
                    "improvement_type": {"type": "string", "description": "One of: general, formal, concise, professional, grammar."},
                    "instruction":      {"type": "string", "description": "Specific improvement instruction to apply."},
                },
                "required": [],
            },
        },
    },

    "export_as_markdown": {
        "type": "function",
        "function": {
            "name": "export_as_markdown",
            "description": (
                "Export content or the last generated document as clean markdown. "
                "Returns the full markdown between BEGIN/END markers. "
                "All parameters optional — will use last generated document if content is empty."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content":        {"type": "string", "description": "Text to export (uses last document if empty)."},
                    "document_title": {"type": "string", "description": "Title for the markdown document (auto-detected if empty)."},
                },
                "required": [],
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register() -> None:
    """Register all Document Agent tools, schemas, and prompt into the framework.

    This function is idempotent — calling it multiple times is safe.
    It is called automatically when document_agent is imported.
    """
    global _registered
    if _registered:
        return

    tool_map = {
        "generate_cv": generate_cv,
        "generate_cover_letter": generate_cover_letter,
        "generate_proposal": generate_proposal,
        "generate_report": generate_report,
        "generate_invoice": generate_invoice,
        "generate_email": generate_email,
        "load_and_summarize": load_and_summarize,
        "answer_from_document": answer_from_document,
        "edit_and_improve": edit_and_improve,
        "export_as_markdown": export_as_markdown,
    }
    missing = set(DOCUMENT_AGENT_CONFIG.tool_names) ^ set(tool_map)
    if missing:
        raise KeyError(f"Document agent tool registration mismatch: {sorted(missing)}")

    # Register tool functions
    TOOL_REGISTRY.update(tool_map)

    # Register schemas
    for name, schema in _DOCUMENT_AGENT_SCHEMAS.items():
        SCHEMA_REGISTRY[name] = schema

    # Register system prompt
    PROMPT_REGISTRY["document_agent"] = DOCUMENT_AGENT_PROMPT
    _registered = True


# Auto-register on import
register()
