import json
from pathlib import Path
from typing import Any, Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)

CONVO_FILE = MEMORY_DIR / "conversation.json"
FACTS_FILE = MEMORY_DIR / "facts.json"

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
    if CONVO_FILE.exists():
        try:
            data = json.loads(CONVO_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


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
    CONVO_FILE.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_message(role: str, content: str) -> None:
    convo = load_conversation()
    convo.append({"role": role, "content": content})
    save_conversation(convo)


def clear_conversation() -> None:
    if CONVO_FILE.exists():
        CONVO_FILE.unlink()


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
            except Exception:
                pass

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
    if not FACTS_FILE.exists():
        return {}

    try:
        raw = json.loads(FACTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

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

    # Persist cleanup when the on-disk representation differs.
    if facts != raw:
        _write_facts(facts)

    return facts


def _write_facts(facts: dict) -> None:
    FACTS_FILE.write_text(
        json.dumps(facts, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_fact(key: str, value: Any) -> None:
    value = _clean_text(value)
    if not value:
        return

    facts = load_facts()
    facts[key] = value
    _write_facts(facts)


def save_fact_list(key: str, value: Any) -> Optional[str]:
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