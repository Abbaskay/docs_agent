"""
registries/schema_registry.py — OpenAI-compatible tool schemas for all tools.

Each schema defines the tool's name, description, and parameter spec
in the OpenAI function-calling format (used by DeepSeek API).

Adding a new tool = one dict entry here matching the tool_registry entry.
"""

SCHEMA_REGISTRY: dict[str, dict] = {
    "get_order_status": {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Retrieve the current status and details of a Hyperzod order. "
                "Returns the order ID, customer name, merchant, items, current status, "
                "and total amount. Use this when a customer asks about their order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID (e.g., 'HZ001').",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    "get_eta": {
        "type": "function",
        "function": {
            "name": "get_eta",
            "description": (
                "Get the estimated delivery time and assigned driver for an order. "
                "Use this when a customer asks when their order will arrive or "
                "who is delivering it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID (e.g., 'HZ001').",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    "request_refund": {
        "type": "function",
        "function": {
            "name": "request_refund",
            "description": (
                "Submit a refund request for a Hyperzod order. Checks eligibility "
                "and processes the request if valid. Use this when a customer "
                "explicitly asks for a refund."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID to refund (e.g., 'HZ002').",
                    },
                    "reason": {
                        "type": "string",
                        "description": "The customer's reason for requesting a refund.",
                    },
                },
                "required": ["order_id", "reason"],
            },
        },
    },
    "escalate_to_human": {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Escalate an unresolved or complex issue to a human support agent "
                "by creating a support ticket. Use this when the customer's problem "
                "cannot be resolved with the available tools, or when they explicitly "
                "request to speak to a human."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID related to the issue.",
                    },
                    "issue_summary": {
                        "type": "string",
                        "description": "A brief summary of the customer's issue for the human agent.",
                    },
                },
                "required": ["order_id", "issue_summary"],
            },
        },
    },
    "search_web": {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for information on a given topic. Returns a summary "
                "of relevant findings. Use this when the user asks a factual question "
                "or wants to look something up."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "calculate": {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate a mathematical expression and return the result. "
                "Supports basic arithmetic: +, -, *, /, **, %, parentheses. "
                "Use this when the user asks to compute something."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The math expression to evaluate (e.g., '(25 * 4) + 10').",
                    },
                },
                "required": ["expression"],
            },
        },
    },
    "get_current_time": {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": (
                "Get the current date and time. Use this when the user asks "
                "what time or date it is."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
}
