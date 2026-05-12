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
from openai import APIConnectionError, APIError, OpenAI, RateLimitError

from core.config import AgentConfig
from core.logger import logger
from core.memory import Memory
from registries.prompt_registry import PROMPT_REGISTRY
from registries.schema_registry import SCHEMA_REGISTRY
from registries.tool_registry import TOOL_REGISTRY

# Load environment variables (DEEPSEEK_API_KEY)
load_dotenv()


def _failure_response(answer: str, iterations: int) -> dict:
    return {
        "answer": answer,
        "success": False,
        "trace": [],
        "iterations": iterations,
        "tool_call_count": 0,
    }


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

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return _failure_response(
            "DEEPSEEK_API_KEY not found. Copy .env.example to .env and add your key.",
            0,
        )

    # Step 1: Create Memory if not provided
    if memory is None:
        memory = Memory()

    # Step 2: Add the user's message to conversation history
    memory.add_user_message(task)

    # Step 3: Look up the system prompt from the registry
    system_prompt = PROMPT_REGISTRY.get(config.prompt_key)
    if not system_prompt:
        return _failure_response(
            f"Prompt '{config.prompt_key}' is not registered for this agent.",
            0,
        )

    # Step 4: Build the tool schema list for only this agent's allowed tools
    missing_schemas = [name for name in config.tool_names if name not in SCHEMA_REGISTRY]
    if missing_schemas:
        return _failure_response(
            f"Tool schema(s) not registered: {', '.join(missing_schemas)}",
            0,
        )
    tool_schemas = [SCHEMA_REGISTRY[name] for name in config.tool_names]

    # Step 5: Initialize the DeepSeek client (OpenAI-compatible)
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    iterations = 0
    agent_trace = []

    # Step 6: Enter the agentic loop
    while iterations < config.max_iterations:
        iterations += 1

        # Trim message history if it grows too large (before building the request)
        if len(memory.messages) > 40:
            logger.log_error(
                config.name,
                "message_history_trimmed",
                f"Trimmed message history from {len(memory.messages)} to last 40 messages",
                iterations,
            )
            memory.messages = memory.messages[-40:]

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

            except RateLimitError as e:
                wait_time = 2 ** attempt
                logger.log_error(config.name, "rate_limit", str(e)[:200], iterations)
                if attempt < 3:
                    time.sleep(wait_time)
                else:
                    return _failure_response(
                        "I'm sorry, the AI service is rate limited right now. Please try again shortly.",
                        iterations,
                    )
            except APIConnectionError as e:
                wait_time = 2 ** attempt
                logger.log_error(config.name, "api_connection_error", str(e)[:200], iterations)
                if attempt < 3:
                    time.sleep(wait_time)
                else:
                    return _failure_response(
                        "I'm sorry, I'm having trouble connecting to my AI service. Please try again in a moment.",
                        iterations,
                    )
            except APIError as e:
                wait_time = 2 ** attempt
                logger.log_error(config.name, "api_error", str(e)[:200], iterations)
                if attempt < 3:
                    time.sleep(wait_time)
                else:
                    return _failure_response(
                        "I'm sorry, the AI service returned an error. Please try again in a moment.",
                        iterations,
                    )
            except Exception as e:
                wait_time = 2 ** attempt
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
                    return _failure_response(
                        (
                            "I'm sorry, I'm having trouble connecting to my AI service. "
                            "Please try again in a moment."
                        ),
                        iterations,
                    )

        # Step 6b: Extract the response
        if not getattr(response, "choices", None):
            logger.log_error(config.name, "empty_response", "Provider returned no choices", iterations)
            break

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
            if not getattr(assistant_message, "tool_calls", None):
                logger.log_error(config.name, "missing_tool_calls", "finish_reason=tool_calls but no tool calls returned", iterations)
                break
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
                try:
                    tool_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError as e:
                    tool_args = {}
                    logger.log_error(config.name, "tool_argument_json", str(e)[:200], iterations)
                if not isinstance(tool_args, dict):
                    logger.log_error(
                        config.name,
                        "tool_argument_type",
                        f"Expected object arguments for {tool_name}, got {type(tool_args).__name__}",
                        iterations,
                    )
                    tool_args = {}
                tool_call_id = tool_call.id

                # Validate that the tool exists in the registry
                if tool_name not in TOOL_REGISTRY:
                    result = f"Tool '{tool_name}' is not available in this agent."
                else:
                    # Execute the tool function, catching any errors
                    try:
                        fn = TOOL_REGISTRY[tool_name]
                        result = fn(**tool_args)
                        if not isinstance(result, str):
                            result = str(result)
                    except Exception as e:
                        result = f"Error executing {tool_name}: {type(e).__name__} — {e}"

                # Log the tool call
                logger.log_tool_call(config.name, tool_name, tool_args, result)

                # Fire the UI callback if provided (for thinking panel)
                if on_tool_call:
                    try:
                        on_tool_call(tool_name, tool_args, result)
                    except Exception as e:
                        logger.log_error(
                            config.name,
                            "on_tool_call_callback",
                            str(e)[:200],
                            iterations,
                        )

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
            + (
                f"Last tool output: {str(agent_trace[-1].get('output', ''))[:500]}"
                if agent_trace
                else "Could you try rephrasing your question?"
            )
        ),
        "trace": agent_trace,
        "iterations": iterations,
        "tool_call_count": memory.tool_call_count,
        "success": False,
    }
