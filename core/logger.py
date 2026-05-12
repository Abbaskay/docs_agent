"""
core/logger.py — Structured logging for the agent framework.

Logs every LLM call, tool call, error, and agent completion to both
console and a JSONL file for observability and debugging.
"""

import json
import threading
from datetime import datetime

_LOG_LOCK = threading.Lock()


class Logger:
    """Structured logger that writes events to console and a JSONL file."""

    def __init__(self, log_file: str = "agent_logs.jsonl"):
        """Initialize the logger with a target log file path."""
        self.log_file = log_file

    def log(self, event_type: str, data: dict) -> None:
        """Write a structured log entry to file and print to console.

        Args:
            event_type: Category of event (e.g. 'llm_call', 'tool_call').
            data:       Key-value pairs describing the event.
        """
        timestamp = datetime.now().isoformat()
        entry = {"timestamp": timestamp, "event": event_type, "data": data}

        # Append as a single JSON line to the log file
        try:
            line = json.dumps(entry) + "\n"
            with _LOG_LOCK:
                with open(self.log_file, "a") as f:
                    f.write(line)
        except Exception:
            pass

        # Pretty-print to console for live observability
        try:
            kv_str = " | ".join(f"{k}={v}" for k, v in data.items())
            print(f"[{timestamp}] [{event_type.upper()}] {kv_str}")
        except Exception:
            pass

    def log_llm_call(
        self,
        agent_name: str,
        model: str,
        iteration: int,
        stop_reason: str,
        input_tokens: int = 0,
    ) -> None:
        """Log an LLM API call."""
        self.log(
            "llm_call",
            {
                "agent": agent_name,
                "model": model,
                "iteration": iteration,
                "stop_reason": stop_reason,
                "input_tokens": input_tokens,
            },
        )

    def log_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
    ) -> None:
        """Log a tool function execution. Output truncated to 200 chars."""
        safe_output = str(tool_output)[:200]
        self.log(
            "tool_call",
            {
                "agent": agent_name,
                "tool": tool_name,
                "input": tool_input,
                "output": safe_output,
            },
        )

    def log_error(
        self,
        agent_name: str,
        error_type: str,
        message: str,
        iteration: int,
    ) -> None:
        """Log an error encountered during agent execution."""
        self.log(
            "error",
            {
                "agent": agent_name,
                "error_type": error_type,
                "message": message,
                "iteration": iteration,
            },
        )

    def log_agent_complete(
        self,
        agent_name: str,
        iterations: int,
        total_tool_calls: int,
    ) -> None:
        """Log successful completion of an agent run."""
        self.log(
            "agent_complete",
            {
                "agent": agent_name,
                "iterations": iterations,
                "total_tool_calls": total_tool_calls,
            },
        )


# Module-level singleton — import this everywhere
logger = Logger()
