"""
core/memory.py — In-memory conversation manager.

Tracks the message history for a single agent session.
Provides helpers for adding user, assistant, and tool result messages.
"""


class Memory:
    """Simple in-memory conversation history manager."""

    def __init__(self):
        """Initialize with an empty message list and zero tool calls."""
        self.messages: list[dict] = []
        self.tool_call_count: int = 0

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content) -> None:
        """Append an assistant message. Content can be a string or list (for tool use blocks)."""
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_results(self, tool_results: list) -> None:
        """Append tool results as a user message and increment the tool call counter."""
        self.messages.append({"role": "user", "content": tool_results})
        self.tool_call_count += len(tool_results)

    def get_messages(self) -> list:
        """Return a copy of the full message history."""
        return list(self.messages)

    def clear(self) -> None:
        """Reset conversation history and tool call counter."""
        self.messages = []
        self.tool_call_count = 0
