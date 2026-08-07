# core/memory_extractor.py

from core.memory import save_fact
from ai.llm import ask_ai
import json

def extract_and_store(text: str):

    text = text.lower()

    # 🧑 Name detection
    if "my name is" in text:
        name = text.split("my name is")[-1].strip()
        save_fact("user_name", name)

    # ❤️ Likes
    if "i like" in text:
        value = text.split("i like")[-1].strip()
        save_fact("likes", value)

    if "my favorite" in text:
        value = text.split("my favorite")[-1].strip()
        save_fact("favorite", value)

    # 😓 Emotion tracking
    if "i am stressed" in text or "i'm stressed" in text:
        save_fact("mood", "stressed")

    if "i am happy" in text:
        save_fact("mood", "happy")

    # 📅 Important events
    if "exam" in text:
        save_fact("important_event", "exam")

    if "interview" in text:
        save_fact("important_event", "interview")

async def ai_extract_memory(text, personality):

    prompt = f"""
Extract user facts.

Return ONLY JSON.

Allowed keys:
    user_name
    likes
    favorite
    mood
    important_event

Input:
{text}

Example:
{{
  "name":"John",
  "likes":"Python"
}}
"""

    response = await ask_ai(
        prompt,
        personality,
        {},
        []
    )

    try:
        return json.loads(response)
    except:
        return {}
