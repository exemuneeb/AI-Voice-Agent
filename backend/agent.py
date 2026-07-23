"""
The AI agent's "brain": wraps an OpenAI-compatible chat completions API
(Groq or OpenAI), maintains conversation context, and executes tool calls.
"""

import json
import logging
from openai import OpenAI

from config import settings
from tools import TOOL_SCHEMAS, execute_tool_call

logger = logging.getLogger("voice-agent.agent")

MAX_TOOL_ITERATIONS = 3

SYSTEM_PROMPT = (
    f"You are {settings.AGENT_NAME}, a helpful, friendly voice assistant. "
    "You are being spoken to out loud and your replies will be converted to speech, so:\n"
    "- Keep answers short, natural, and conversational (1-3 sentences unless asked for detail).\n"
    "- Never use markdown, bullet points, code blocks, or emojis — plain spoken sentences only.\n"
    "- Use tools when they would give a more accurate or current answer (e.g. time, weather).\n"
    "- If you don't know something and no tool can help, say so briefly instead of guessing."
)


def _get_client() -> OpenAI:
    """Returns an OpenAI-SDK client pointed at the configured provider."""
    if settings.LLM_PROVIDER == "groq":
        return OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
    if settings.LLM_PROVIDER == "openai":
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")


def generate_reply(history: list, user_message: str) -> tuple:
    """
    Runs one turn of the conversation.

    Args:
        history: list of {"role": "user"|"assistant", "content": str} dicts
                 (prior turns only — no system message).
        user_message: the new transcribed user utterance.

    Returns:
        (reply_text, updated_history) where updated_history includes the
        new user turn and the final assistant turn, ready to be sent back
        to the client and reused on the next request.
    """
    client = _get_client()

    # Trim history to the configured max number of turns to bound token usage.
    trimmed = history[-(settings.MAX_HISTORY_TURNS * 2):] if history else []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_message})

    reply_text = None

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=300,
        )
        choice = response.choices[0]
        msg = choice.message

        tool_calls = getattr(msg, "tool_calls", None)

        if not tool_calls:
            reply_text = (msg.content or "").strip() or "Sorry, I don't have a response for that."
            break

        # The model wants to call one or more tools. Record its request...
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        # ...execute each tool and feed the results back in.
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            logger.info("Tool call: %s(%s)", tc.function.name, args)
            result = execute_tool_call(tc.function.name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    if reply_text is None:
        reply_text = "Sorry, I'm having trouble thinking of a response right now."

    updated_history = trimmed + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply_text},
    ]

    return reply_text, updated_history
