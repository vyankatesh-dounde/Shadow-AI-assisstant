import asyncio
import requests
from config import OLLAMA_URL, OLLAMA_MODEL

# Canned replies ask_ai() can return when something goes wrong. brain.py
# skips saving these into conversation.json - a small model like phi3
# will otherwise sometimes read its own past "I'm offline right now."
# turn and try to continue/explain it instead of answering the new
# question (this is exactly what produced the garbled "If the user
# asks again... Relationship Level" reply).
FALLBACK_REPLIES = frozenset({
    "I'm offline right now.",
    "Something went wrong. Please try again.",
    "Say that again.",
})


def _call_ollama(payload):
    """Blocking network call - run via asyncio.to_thread so it never
    freezes the FastAPI event loop (and every other connected browser)
    while Ollama is thinking."""
    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    return response.json()


async def ask_ai(text, personality, facts, conversation):
    system_prompt = f"""
You are Shadow.

You are calm, confident, slightly mysterious.
Speak like a real human.
Never explain how you are responding.
Never say phrases like "As Shadow" or describe your tone.
Rules:
- Give direct answers.
- Keep responses short unless asked for detail.
- For math or facts, respond with just the answer.
- Sound natural, like a real assistant (similar to JARVIS).
Never continue the conversation yourself.
Never generate follow-up questions unless asked.
Adjust response length based on question.
{personality.build_prompt()}
"""

    history = ""

    for msg in conversation[-12:]:
        role = "Shadow" if msg["role"] == "assistant" else "User"
        history += f"{role}: {msg['content']}\n"

    full_prompt = f"""
    {system_prompt}

    Use conversation history when relevant.
    Do not repeat previous answers unnecessarily.

    Conversation History:
    {history}

    User: {text}
    Shadow:
    """

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False   # ✅ VERY IMPORTANT
    }

    try:
        data = await asyncio.to_thread(_call_ollama, payload)

        reply = data.get("response", "")

        reply = reply.strip()

        # 🚫 BLOCK PROMPT INJECTION / GARBAGE
        bad_patterns = [
            "your task is",
            "embody",
            "you must",
            "instruction",
            "---",
            "relationship level",   # leaked from our own injected context
            "the user asks",
            ]

        for pattern in bad_patterns:
            if pattern in reply.lower():
                return "Something went wrong. Please try again."

        # REMOVE CHAT LEAKS
        for stop_word in ["User:", "Shadow:"]:
            if stop_word in reply:
                reply = reply.split(stop_word)[0]

        return reply.strip() or "Say that again."

    except Exception as e:
        print("ERROR:", e)
        return "I'm offline right now."
