"""
registries/tool_registry.py — Central registry of all tool functions.

Maps tool name strings to their actual Python callables.
Adding a new tool = one import + one dict entry here.
"""

from tools.hyperzod_tools import (
    escalate_to_human,
    get_eta,
    get_order_status,
    request_refund,
)
from tools.general_tools import (
    calculate,
    get_current_time,
    search_web,
)

TOOL_REGISTRY: dict[str, callable] = {
    # Hyperzod order support tools
    "get_order_status": get_order_status,
    "get_eta": get_eta,
    "request_refund": request_refund,
    "escalate_to_human": escalate_to_human,
    # General-purpose tools
    "search_web": search_web,
    "calculate": calculate,
    "get_current_time": get_current_time,
}
