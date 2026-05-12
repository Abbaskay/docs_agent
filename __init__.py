"""
document_agent/__init__.py — Auto-registration entry point.

Importing document_agent (or any of its submodules) triggers config.py
which calls register() and injects all tools, schemas, and the system
prompt into the shared framework registries.
"""

from config import DOCUMENT_AGENT_CONFIG, register

register()

__all__ = ["DOCUMENT_AGENT_CONFIG", "register"]
