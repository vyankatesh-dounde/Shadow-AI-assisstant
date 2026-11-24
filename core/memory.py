import json
from datetime import datetime, timezone
from pathlib import Path
from memory.storage import (
    load_conversation as _db_load_conversation,
    append_message as _db_append_message,
    clear_conversation as _db_clear_conversation,
    get_kv,
    set_kv,
)
from typing import Any, Iterable, Optional
import random
import time
from datetime import date, datetime as dt, timedelta, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)

CONVO_FILE = MEMORY_DIR / "conversation.json"
FACTS_FILE = MEMORY_DIR / "facts.json"
PREFERENCES_FILE = MEMORY_DIR / "preferences.json"

WAKE_WORDS = [
    "hey shadow", "shadow", "हे शॅडो", "हाय शॅडो", "शॅडो"
]
ACKNOWLEDGMENTS = ["हो, सांगा.", "बोला.", "मी ऐकत आहे.", "काय मदत हवी?"]

# Keep the existing conversation contract so the rest of Shadow remains compatible.
MAX_TURNS = 6

# Memory v2 keeps the public JSON keys compatible with the current project:
# user_name, like, favorite, dislike, mood, important_event.
#
# The important change is that likes/dislikes are treated as CURRENT
# preferences. Adding a dislike automatically removes the same item from
# likes, and adding a like automatically removes it from dislikes.


# =========================================================
# 💬 SHORT-TERM MEMORY
# =========================================================

def load_conversation() -> list[dict]:
    return _db_load_conversation()


def save_conversation(convo: list[dict]) -> None:
    clean = []
    for msg in convo:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        clean.append({"role": role, "content": content})

    clean = clean[-MAX_TURNS * 2:]
    _db_clear_conversation()
    for msg in clean:
        _db_append_message(msg["role"], msg["content"])


def add_message(role: str, content: str) -> None:
    _db_append_message(role, content)


def clear_conversation() -> None:
    _db_clear_conversation()


# =========================================================
# 🧠 LONG-TERM MEMORY
# =========================================================

def _clean_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    # Repair common old JSON-as-string corruption such as
    # "['the Beatles']" or "[\"the Beatles\"]".
    if len(value) >= 2 and value[0] == "[" and value[-1] == "]":
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list) and parsed:
                parts = [_clean_text(v) for v in parsed]
                parts = [p for p in parts if p]
                if parts:
                    return ", ".join(parts)
        except Exception:
            # Older files may use Python-style single quotes.
            inner = value[1:-1].strip()
            if len(inner) >= 2 and inner[0] == "'" and inner[-1] == "'":
                return inner[1:-1].strip() or None

    return value


def _normalize_item(value: Any) -> Optional[str]:
    """Convert a preference into a clean display string.

    Handles old corrupted values such as:
        "['Beatles']"
        '["pizza"]'
    """
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        # Repair the common corruption created by older versions.
        if len(value) >= 2 and value[0] == "[" and value[-1] == "]":
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    parts = [_normalize_item(v) for v in parsed]
                    parts = [p for p in parts if p]
                    return ", ".join(parts) if parts else None
            except json.JSONDecodeError:
                # Older releases wrote Python-style list strings, e.g.
                # "['Beatles']". Parse only that narrow legacy shape.
                inner = value[1:-1].strip()
                if len(inner) >= 2 and inner[0] == "'" and inner[-1] == "'":
                    return inner[1:-1].strip() or None

        return value

    return None


def _clean_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]

    if not isinstance(values, list):
        return []

    result = []
    seen = set()

    for raw in values:
        item = _normalize_item(raw)
        if not item:
            continue

        # Remove obvious old extractor garbage.
        garbage = {
            "and what do i like",
            "and what do i hate",
            "what do i like",
            "what do i hate",
        }
        if item.lower() in garbage:
            continue

        key = item.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def _same_item(a: str, b: str) -> bool:
    """Conservative matching for preference changes."""
    a = a.strip().casefold()
    b = b.strip().casefold()

    if not a or not b:
        return False

    return a == b or a in b or b in a


def _remove_matching(items: Iterable[str], value: str) -> tuple[list[str], list[str]]:
    remaining = []
    removed = []

    for item in items:
        if _same_item(item, value):
            removed.append(item)
        else:
            remaining.append(item)

    return remaining, removed


def load_facts() -> dict:
    raw = get_kv("facts", {})

    if not isinstance(raw, dict):
        return {}

    # Normalize the existing file in memory. This lets old memory continue
    # working without requiring a manual migration script.
    facts = {}

    for key in ("user_name", "favorite", "mood", "important_event"):
        value = _clean_text(raw.get(key))
        if value:
            facts[key] = value

    for key in ("like", "dislike"):
        cleaned = _clean_list(raw.get(key))
        if cleaned:
            facts[key] = cleaned

    # Enforce the Memory v2 invariant:
    # one item cannot be both a current like and a current dislike.
    likes = facts.get("like", [])
    dislikes = facts.get("dislike", [])

    if likes and dislikes:
        clean_likes = []
        for like in likes:
            if not any(_same_item(like, dislike) for dislike in dislikes):
                clean_likes.append(like)

        if clean_likes:
            facts["like"] = clean_likes
        else:
            facts.pop("like", None)

    if facts != raw:
        set_kv("facts", facts)

    return facts


def _write_facts(facts: dict) -> None:
    set_kv("facts", facts)


def load_preferences() -> dict:
    value = get_kv("preferences", {})
    return value if isinstance(value, dict) else {}


def _write_preferences(preferences: dict) -> None:
    set_kv("preferences", preferences)


def _record_preference(key: str, value: str, source: str, active: bool) -> None:
    preferences = load_preferences()
    history = preferences.setdefault(key, [])
    history.append({
        "value": value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "active": active,
    })
    _write_preferences(preferences)


def save_fact(key: str, value: Any) -> None:
    value = _clean_text(value)
    if not value:
        return

    facts = load_facts()
    facts[key] = value
    _write_facts(facts)


def save_fact_list(key: str, value: Any, source: str = "explicit") -> Optional[str]:
    """Add a current preference and resolve conflicts automatically.

    Returns the clean value that was stored, or None if nothing was stored.
    """
    if key not in {"like", "dislike"}:
        return None

    value = _normalize_item(value)
    if not value:
        return None

    facts = load_facts()

    current = _clean_list(facts.get(key, []))

    if not any(_same_item(item, value) for item in current):
        current.append(value)

    facts[key] = current

    # Current preferences are mutually exclusive.
    opposite = "dislike" if key == "like" else "like"
    opposite_items = _clean_list(facts.get(opposite, []))
    opposite_items, _ = _remove_matching(opposite_items, value)

    if opposite_items:
        facts[opposite] = opposite_items
    else:
        facts.pop(opposite, None)

    _write_facts(facts)
    _record_preference(key, value, source, True)
    return value


def remove_fact_list(key: str, value: Any) -> Optional[str]:
    """Remove a current preference. Returns the original removed value."""
    if key not in {"like", "dislike"}:
        return None

    value = _normalize_item(value)
    if not value:
        return None

    facts = load_facts()
    current = _clean_list(facts.get(key, []))

    remaining, removed = _remove_matching(current, value)

    if remaining:
        facts[key] = remaining
    else:
        facts.pop(key, None)

    _write_facts(facts)
    if removed:
        _record_preference(key, removed[0], "explicit removal", False)
    return removed[0] if removed else None


def remove_favorite_if_matches(value: Any) -> Optional[str]:
    value = _normalize_item(value)
    if not value:
        return None

    facts = load_facts()
    favorite = facts.get("favorite")

    if not isinstance(favorite, str):
        return None

    if _same_item(favorite, value):
        facts.pop("favorite", None)
        _write_facts(facts)
        return favorite

    return None


def update_relationship(text: str) -> dict:
    data = load_relationship()
    score = 0
    lower = text.lower()
    if "thank" in lower:
        score += 2
    if "good job" in lower or "nice" in lower:
        score += 2
    if "i like you" in lower:
        score += 4
    if "i am sad" in lower or "i'm sad" in lower:
        score += 3
    if "i am stressed" in lower:
        score += 3
    data["points"] = data.get("points", 0) + score
    if data["points"] > 20:
        data["level"] = 2
    if data["points"] > 50:
        data["level"] = 3
    if data["points"] > 100:
        data["level"] = 4
    if data["points"] > 200:
        data["level"] = 5
    set_kv("relationship", data)
    return data


def load_relationship() -> dict:
    data = get_kv("relationship", {"level": 1, "points": 0, "last_interaction": None})
    return data if isinstance(data, dict) else {"level": 1, "points": 0, "last_interaction": None}


def is_wake_word(text: str) -> bool:
    return text.strip().lower().rstrip("!?.") in WAKE_WORDS


def handle_wake_word(text: str) -> str:
    del text
    state = get_kv("wake_state", {})
    if not isinstance(state, dict):
        state = {}
    today = date.today().isoformat()
    if state.get("last_greeted_date") != today:
        state["last_greeted_date"] = today
        set_kv("wake_state", state)
        hour = dt.now().hour
        part = "शुभ सकाळ" if hour < 12 else ("शुभ दुपार" if hour < 18 else "शुभ संध्याकाळ")
        return f"{part}. सांगा, काय मदत हवी?"
    return random.choice(ACKNOWLEDGMENTS)


def save_daily_summary(conversation: list[dict]) -> None:
    if not conversation:
        return
    summary = "We talked about " + ", ".join(
        msg["content"][:25] for msg in conversation if msg.get("role") == "user"
    )
    data = get_kv("daily_memory", {})
    if not isinstance(data, dict):
        data = {}
    data[date.today().isoformat()] = {"summary": summary, "timestamp": time.time()}
    set_kv("daily_memory", data)


def load_daily_summary(day: str | None = None) -> dict | None:
    data = get_kv("daily_memory", {})
    if not isinstance(data, dict):
        return None
    record = data.get(day or date.today().isoformat())
    return record if isinstance(record, dict) else None
