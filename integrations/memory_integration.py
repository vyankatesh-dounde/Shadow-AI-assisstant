from core.memory import load_facts
from core.memory_extractor import extract_and_store, build_fact_ack
from integrations.daily_memory import (
    load_daily_summary,
    save_daily_summary as _save_daily_summary,
)


# =========================================================
# 🧠 MEMORY INTEGRATION
# =========================================================

def learn_from_text(text: str) -> dict:
    return extract_and_store(text)


def fact_ack(changes: dict):
    return build_fact_ack(changes)


def build_memory_context() -> str:
    """Build a compact, current-memory context for the LLM.

    Only current preferences are exposed. Conflicting/duplicate entries
    are already cleaned by core.memory.load_facts().
    """
    facts = load_facts()
    context_parts = []

    user_name = facts.get("user_name")
    if user_name:
        context_parts.append(f"User name is {user_name}.")

    likes = facts.get("like", [])
    if isinstance(likes, list) and likes:
        context_parts.append(f"User currently likes: {', '.join(likes)}.")

    dislikes = facts.get("dislike", [])
    if isinstance(dislikes, list) and dislikes:
        context_parts.append(
            f"User currently dislikes: {', '.join(dislikes)}."
        )

    favorite = facts.get("favorite")
    if favorite:
        context_parts.append(f"User's current favorite is {favorite}.")

    mood = facts.get("mood")
    if mood:
        context_parts.append(f"User previously said they felt {mood}.")

    important_event = facts.get("important_event")
    if important_event:
        context_parts.append(
            f"User has an important {important_event} coming up."
        )

    return " ".join(context_parts)


def get_daily_memory():
    daily = load_daily_summary()

    if daily:
        summary = daily.get("last_summary")
        if summary:
            return f"You seemed busy yesterday… {summary}"

    return None


def remember_today(conversation):
    _save_daily_summary(conversation)