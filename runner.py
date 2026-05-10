"""
core/runner.py — The shared agent orchestration engine.

This is the heart of the framework. It powers every agent regardless
of persona or tools. The runner never checks which config it received —
it simply follows the config's instructions.

Uses the OpenAI-compatible API pointed at DeepSeek.
"""

import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from core.config import AgentConfig
from core.logger import logger
from core.memory import Memory
from registries.prompt_registry import PROMPT_REGISTRY
from registries.schema_registry import SCHEMA_REGISTRY
from registries.tool_registry import TOOL_REGISTRY

# Load environment variables (DEEPSEEK_API_KEY)
load_dotenv()


def run_agent(
    task: str,
    config: AgentConfig,
    memory: Memory = None,
    on_tool_call=None,
) -> dict:
    """The shared agent engine. Powers every agent in the framework.

    Args:
        task:         The user's input message or subtask description.
        config:       AgentConfig defining this agent's identity and tools.
        memory:       Memory instance (creates a new one if None).
        on_tool_call: Optional callback fn(tool_name, tool_input, tool_output)
                      called after each tool execution — used by the UI for
                      live thinking panel updates.

    Returns:
        dict with keys:
            answer:          str  — the agent's final text response
            trace:           list — every tool call with name/input/output
            iterations:      int  — how many LLM calls were made
            tool_call_count: int  — total tools executed
            success:         bool — True if completed, False if max iterations hit
    """

    # Step 1: Create Memory if not provided
    if memory is None:
        memory = Memory()

    # Step 2: Add the user's message to conversation history
    memory.add_user_message(task)

    # Step 3: Look up the system prompt from the registry
    system_prompt = PROMPT_REGISTRY[config.prompt_key]

    # Step 4: Build the tool schema list for only this agent's allowed tools
    tool_schemas = [
        SCHEMA_REGISTRY[name]
        for name in config.tool_names
        if name in SCHEMA_REGISTRY
    ]

    # Step 5: Initialize the DeepSeek client (OpenAI-compatible)
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    iterations = 0
    agent_trace = []

    # Step 6: Enter the agentic loop
    while iterations < config.max_iterations:
        iterations += 1

        # Step 6a: Call the LLM with exponential backoff retry (max 3 attempts)
        response = None
        for attempt in range(1, 4):
            try:
                # Build messages with system prompt prepended
                full_messages = [
                    {"role": "system", "content": system_prompt}
                ] + memory.get_messages()

                # Make the API call
                api_kwargs = {
                    "model": config.model,
                    "messages": full_messages,
                    "max_tokens": config.max_tokens,
                }
                # Only include tools if the agent has any
                if tool_schemas:
                    api_kwargs["tools"] = tool_schemas
                    api_kwargs["tool_choice"] = "auto"

                response = client.chat.completions.create(**api_kwargs)
                break  # Success — exit retry loop

            except Exception as e:
                wait_time = 2 ** attempt  # 2s, 4s, 8s
                logger.log_error(
                    config.name,
                    type(e).__name__,
                    str(e)[:200],
                    iterations,
                )
                if attempt < 3:
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    return {
                        "answer": (
                            "I'm sorry, I'm having trouble connecting to my AI service. "
                            "Please try again in a moment."
                        ),
                        "trace": agent_trace,
                        "iterations": iterations,
                        "tool_call_count": memory.tool_call_count,
                        "success": False,
                    }

        # Step 6b: Extract the response
        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # Step 6c: Log the LLM call
        logger.log_llm_call(
            config.name,
            config.model,
            iterations,
            finish_reason,
            input_tokens=getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        )

        # Step 6d: CASE A — Model is done, return the final text answer
        if finish_reason == "stop":
            final_text = assistant_message.content or ""
            logger.log_agent_complete(
                config.name, iterations, memory.tool_call_count
            )
            return {
                "answer": final_text,
                "trace": agent_trace,
                "iterations": iterations,
                "tool_call_count": memory.tool_call_count,
                "success": True,
            }

        # Step 6e: CASE B — Model wants to call tools
        elif finish_reason == "tool_calls":
            # Serialize the assistant message to a plain dict before storing.
            # The raw ChatCompletionMessage object can't be re-sent to the API.
            assistant_dict = {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in assistant_message.tool_calls
                ],
            }
            memory.messages.append(assistant_dict)

            # Process each tool call
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id

                # Validate that the tool exists in the registry
                if tool_name not in TOOL_REGISTRY:
                    result = f"Error: Unknown tool '{tool_name}'"
                else:
                    # Execute the tool function, catching any errors
                    try:
                        fn = TOOL_REGISTRY[tool_name]
                        result = fn(**tool_args)
                    except Exception as e:
                        result = f"Error executing {tool_name}: {type(e).__name__} — {e}"

                # Log the tool call
                logger.log_tool_call(config.name, tool_name, tool_args, result)

                # Fire the UI callback if provided (for thinking panel)
                if on_tool_call:
                    on_tool_call(tool_name, tool_args, result)

                # Record in the trace for the return value
                agent_trace.append(
                    {"tool": tool_name, "input": tool_args, "output": result}
                )

                # Build the tool result message for the API
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result,
                    }
                )

            # Add tool results to memory — each as a separate message
            # (DeepSeek/OpenAI format requires individual tool messages)
            for tr in tool_results:
                memory.messages.append(tr)
            memory.tool_call_count += len(tool_results)

            # Continue the loop — LLM will process tool results next

        # Step 6f: CASE C — Unexpected finish reason
        else:
            logger.log_error(
                config.name,
                "unexpected_finish_reason",
                f"Got: {finish_reason}",
                iterations,
            )
            break

    # Step 7: Max iterations reached without a final answer
    logger.log_error(
        config.name,
        "max_iterations",
        f"Reached {config.max_iterations} iterations without completing",
        iterations,
    )
    return {
        "answer": (
            "I've been thinking about this for a while but couldn't reach a final answer. "
            "Could you try rephrasing your question?"
        ),
        "trace": agent_trace,
        "iterations": iterations,
        "tool_call_count": memory.tool_call_count,
        "success": False,
    }
