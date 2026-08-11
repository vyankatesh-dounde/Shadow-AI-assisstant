from core.memory import load_facts
from core.memory_extractor import extract_and_store, build_fact_ack
from integrations.daily_memory import load_daily_summary, save_daily_summary as _save_daily_summary


# 🧠 Learn from user input.
# Returns the dict of what extract_and_store() actually changed (e.g.
# {"like_added": "pizza"}) so brain.py can short-circuit to a quick
# canned reply for plain fact statements instead of routing them to
# the LLM. An empty dict means nothing recognizable was in the message.
def learn_from_text(text: str) -> dict:
    return extract_and_store(text)


# Re-exported here so brain.py can build a short ack from whatever
# learn_from_text() just returned without importing core.memory_extractor
# directly.
def fact_ack(changes: dict):
    return build_fact_ack(changes)


# 🧠 Build memory context for AI
def build_memory_context():
    facts = load_facts()

    context_parts = []

    if "user_name" in facts:
        context_parts.append(f"User name is {facts['user_name']}.")

    like = facts.get("like")
    if isinstance(like, list) and like:
        context_parts.append(f"User like: {', '.join(like)}.")
    elif isinstance(like, str) and like:
        context_parts.append(f"User like {like}.")  # pre-accumulation data

    dislike = facts.get("dislike")
    if isinstance(dislike, list) and dislike:
        context_parts.append(f"User dislike: {', '.join(dislike)}.")
    elif isinstance(dislike, str) and dislike:
        context_parts.append(f"User dislike {dislike}.")

    if "favorite" in facts:
        context_parts.append(f"User's favorite: {facts['favorite']}.")

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