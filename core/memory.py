# core/memory.py
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"

MEMORY_DIR.mkdir(exist_ok=True)

CONVO_FILE = MEMORY_DIR / "conversation.json"
FACTS_FILE = MEMORY_DIR / "facts.json"

MAX_TURNS = 6  # last 6 exchanges

# Note: daily-summary memory (used by "what happened yesterday") lives
# in integrations/daily_memory.py, not here - it used to be duplicated
# in both places, but only the integrations copy was ever actually used.

# =========================
# 💬 SHORT-TERM MEMORY
# =========================

def load_conversation():
    if CONVO_FILE.exists():
        try:
            return json.loads(CONVO_FILE.read_text())
        except Exception:
            return []
    return []


def save_conversation(convo):
    convo = convo[-MAX_TURNS * 2:]  # user + assistant
    CONVO_FILE.write_text(json.dumps(convo, indent=2))


def add_message(role, content):
    convo = load_conversation()
    convo.append({"role": role, "content": content})
    save_conversation(convo)


def clear_conversation():
    if CONVO_FILE.exists():
        CONVO_FILE.unlink()


# =========================
# 🧠 LONG-TERM MEMORY
# =========================

def load_facts():
    if FACTS_FILE.exists():
        try:
            return json.loads(FACTS_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_fact_list(key, value):
    """Append `value` to a list-valued fact instead of overwriting it.
    Used for facts that accumulate over time (like, dislike) rather
    than replace (user_name, mood). De-dupes case-insensitively so
    saying "I like pizza" twice doesn't create two entries, and skips
    empty captures so a bad extraction doesn't pollute the list."""
    facts = load_facts()
    existing = facts.get(key)

    if isinstance(existing, list):
        items = existing
    elif isinstance(existing, str) and existing:
        items = [existing]  # migrate a fact saved before accumulation existed
    else:
        items = []

    value = (value or "").strip()
    if value and value.lower() not in (v.lower() for v in items):
        items.append(value)

    facts[key] = items
    FACTS_FILE.write_text(json.dumps(facts, indent=2))

def remove_fact_list(key, value):
    """Remove an item from a list-valued fact. Matches loosely (case-
    insensitive substring either direction) since the spoken phrase
    rarely matches the originally-stored text word-for-word - e.g.
    stored "pizza" should be removed by "I don't like pizza anymore"
    even though the captured phrase includes "anymore". Returns the
    removed item's original stored text, or None if nothing matched."""
    facts = load_facts()
    existing = facts.get(key)

    if not isinstance(existing, list) or not existing:
        return None

    value = (value or "").strip().lower()
    if not value:
        return None

    for item in existing:
        item_l = item.lower()
        if item_l in value or value in item_l:
            existing.remove(item)
            facts[key] = existing
            FACTS_FILE.write_text(json.dumps(facts, indent=2))
            return item

    return None

def save_fact(key, value):
    facts = load_facts()
    facts[key] = value
    FACTS_FILE.write_text(json.dumps(facts, indent=2))
