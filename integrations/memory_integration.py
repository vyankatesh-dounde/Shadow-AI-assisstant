# integrations/memory_integration.py

from core.memory import load_facts
from core.memory_extractor import extract_and_store
from integrations.daily_memory import load_daily_summary, save_daily_summary as _save_daily_summary


# 🧠 Learn from user input
def learn_from_text(text: str):
    extract_and_store(text)


# 🧠 Build memory context for AI
def build_memory_context():
    facts = load_facts()

    context_parts = []

    if "user_name" in facts:
        context_parts.append(f"User name is {facts['user_name']}.")

    if "likes" in facts:
        context_parts.append(f"User likes {facts['likes']}.")

    if "mood" in facts:
        context_parts.append(f"User mood earlier was {facts['mood']}.")

    if "important_event" in facts:
        context_parts.append(f"User has {facts['important_event']} coming up.")

    return " ".join(context_parts)


# 📅 Daily recall line
def get_daily_memory():
    daily = load_daily_summary()

    if daily:
        return f"You seemed busy yesterday… {daily['last_summary']}"

    return None


# 📅 Refresh today's summary so get_daily_memory() has something to
# read tomorrow. This used to exist in daily_memory.py but nothing
# ever called it, so "what happened yesterday" always returned nothing.
def remember_today(conversation):
    _save_daily_summary(conversation)
