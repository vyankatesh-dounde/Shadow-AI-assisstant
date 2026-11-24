import asyncio
import json

import httpx
from config import LLAMA_CPP_MODEL, LLAMA_CPP_URL

# Canned replies ask_ai() can return when something goes wrong. brain.py
# skips saving these into conversation.json - a small local model
# will otherwise sometimes read its own past "I'm offline right now."
# turn and try to continue/explain it instead of answering the new
# question (this is exactly what produced the garbled "If the user
# asks again... Relationship Level" reply).
FALLBACK_REPLIES = frozenset({
    "I'm offline right now.",
    "Something went wrong. Please try again.",
    "Say that again.",
})


_http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(60.0, connect=10.0),
    limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
)


async def _iter_llama_cpp_chunks(payload):
    """Yield content chunks from llama.cpp's OpenAI-compatible SSE stream."""
    async with _http_client.stream("POST", LLAMA_CPP_URL, json=payload) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_line = line[len("data:"):].strip()
            if data_line == "[DONE]":
                break
            try:
                data = json.loads(data_line)
            except json.JSONDecodeError:
                continue
            choices = data.get("choices", [])
            if not choices:
                continue
            content = choices[0].get("delta", {}).get("content")
            if isinstance(content, str) and content:
                yield content


async def ask_ai(text, personality, facts, conversation, on_chunk=None):
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
- Understand Marathi and Romanized Marathi, and always reply in Marathi using Devanagari script, even when the user writes in English.
- Keep code, URLs, names, and technical identifiers unchanged when needed.
Never continue the conversation yourself.
Never generate follow-up questions unless asked.
Adjust response length based on question.
{personality.build_prompt()}
"""

    messages = [{
        "role": "system",
        "content": (
            f"{system_prompt}\n"
            "Use conversation history when relevant.\n"
            "Do not repeat previous answers unnecessarily."
        ),
    }]
    for msg in conversation[-6:]:
        role = "assistant" if msg["role"] == "assistant" else "user"
        content = msg["content"]
        if isinstance(content, str):
            messages.append({"role": role, "content": content[-1000:]})
    messages.append({"role": "user", "content": text})

    payload = {
        "model": LLAMA_CPP_MODEL,
        "messages": messages,
        "stream": True,
    }

    try:
        if on_chunk is None:
            reply = "".join([chunk async for chunk in _iter_llama_cpp_chunks(payload)])
        else:
            buffer = []
            async for text_piece in _iter_llama_cpp_chunks(payload):
                buffer.append(text_piece)
                result = on_chunk(text_piece)
                if asyncio.iscoroutine(result):
                    await result
            reply = "".join(buffer)

        reply = reply.strip()

        # REMOVE CHAT LEAKS
        for stop_word in ["User:", "Shadow:"]:
            if stop_word in reply:
                reply = reply.split(stop_word)[0]

        return reply.strip() or "Say that again."

    except Exception as e:
        print("ERROR:", e)
        return "I'm offline right now."
