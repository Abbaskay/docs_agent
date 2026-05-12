"""
core/config.py — AgentConfig dataclass.

Defines the configuration structure for any agent in the framework.
Adding a new agent = creating a new AgentConfig instance.
"""

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Configuration for a single agent persona.

    Attributes:
        name:            Unique agent identifier (matches prompt_key by convention).
        prompt_key:      Key into PROMPT_REGISTRY for this agent's system prompt.
        tool_names:      List of tool name strings this agent is allowed to use.
        model:           LLM model identifier.
        max_tokens:      Maximum tokens per LLM response.
        max_iterations:  Safety limit on agentic loop iterations.
        description:     Human-readable description shown in the UI.
    """

    name: str
    prompt_key: str
    tool_names: list[str] = field(default_factory=list)
    model: str = "deepseek-chat"
    max_tokens: int = 1024
    max_iterations: int = 10
    description: str = ""
