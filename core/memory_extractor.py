import json
import re

from ai.llm import ask_ai
from core.memory import (
    remove_favorite_if_matches,
    remove_fact_list,
    save_fact,
    save_fact_list,
)


# =========================================================
# 🧠 MEMORY V2 — DETERMINISTIC EXTRACTION
# =========================================================

_LIKE_POSITIVE = (
    "i like ",
    "i love ",
    "i enjoy ",
    "i'm into ",
    "i am into ",
)

_LIKE_NEGATIVE = (
    "i don't like ",
    "i do not like ",
    "i dont like ",
    "i no longer like ",
    "i no longer love ",
    "i no longer enjoy ",
    "i'm not into ",
    "i am not into ",
)

_DISLIKE_POSITIVE = (
    "i hate ",
    "i dislike ",
)

_DISLIKE_NEGATIVE = (
    "i don't hate ",
    "i do not hate ",
    "i dont hate ",
    "i don't dislike ",
    "i do not dislike ",
    "i dont dislike ",
    "i no longer hate ",
    "i no longer dislike ",
)

_FAVORITE_PATTERNS = (
    "my favorite is ",
    "my favourite is ",
    "my favorite ",
    "my favourite ",
)

_QUESTION_STARTERS = (
    "what",
    "do i",
    "does",
    "am i",
    "is my",
    "how",
    "why",
    "when",
    "which",
    "who",
    "can you tell me",
    "tell me what",
)

_MOOD_TRIGGERS = {
    "stressed": ("i am stressed", "i'm stressed", "i feel stressed"),
    "happy": ("i am happy", "i'm happy", "i feel happy"),
    "sad": ("i am sad", "i'm sad", "i feel sad"),
    "tired": ("i am tired", "i'm tired", "i feel tired"),
    "anxious": ("i am anxious", "i'm anxious", "i feel anxious"),
}

_EVENT_TRIGGERS = {
    "exam": ("exam",),
    "interview": ("interview",),
    "appointment": ("appointment",),
    "deadline": ("deadline",),
}


def _looks_like_question(lower: str) -> bool:
    stripped = lower.strip()

    if stripped.endswith("?"):
        return True

    return any(
        stripped.startswith(starter + " ") or stripped == starter
        for starter in _QUESTION_STARTERS
    )


def _capture_after(lower: str, phrase: str) -> str:
    value = lower.split(phrase, 1)[-1].strip()

    # Stop at sentence boundaries and obvious conjunctions.
    value = re.split(r"[.,!?;]", value, maxsplit=1)[0]
    value = re.split(r"\s+\bbut\b\s+", value, maxsplit=1)[0]
    value = re.split(r"\s+\balthough\b\s+", value, maxsplit=1)[0]

    # Remove common correction/removal filler.
    value = re.sub(r"\s+(anymore|any more|now)$", "", value).strip()

    # Remove a leading "to" accidentally captured after a phrase.
    value = re.sub(r"^to\s+", "", value).strip()

    return value


def _match_first(lower: str, patterns: tuple[str, ...]):
    for phrase in patterns:
        if phrase in lower:
            return phrase
    return None


def _record_like(value: str, changes: dict) -> None:
    stored = save_fact_list("like", value)
    if stored:
        changes["like_added"] = stored


def _record_dislike(value: str, changes: dict) -> None:
    stored = save_fact_list("dislike", value)
    if stored:
        changes["dislike_added"] = stored


def _remove_like(value: str, changes: dict) -> None:
    removed = remove_fact_list("like", value)
    if removed:
        changes["like_removed"] = removed

    # A strong "I don't like X anymore" statement also invalidates X as
    # the current favorite when the favorite points to the same thing.
    favorite_removed = remove_favorite_if_matches(value)
    if favorite_removed:
        changes["favorite_removed"] = favorite_removed


def _remove_dislike(value: str, changes: dict) -> None:
    removed = remove_fact_list("dislike", value)
    if removed:
        changes["dislike_removed"] = removed


def extract_and_store(text: str) -> dict:
    """Extract current user facts without treating questions as facts.

    Memory v2 guarantees:
      - questions do not modify memory;
      - likes and dislikes cannot contain the same current item;
      - negative preference statements remove old positive preferences;
      - old malformed preference entries are cleaned by memory.py;
      - plain fact statements return a small change dict for brain.py.
    """
    lower = text.lower().strip()
    changes = {}
    is_question = _looks_like_question(lower)

    # ---------------------------------------------------------
    # Name
    # ---------------------------------------------------------
    if not is_question and "my name is " in lower:
        name = _capture_after(lower, "my name is ")
        if name:
            clean_name = name.title()
            save_fact("user_name", clean_name)
            changes["user_name"] = clean_name

    # ---------------------------------------------------------
    # Preferences
    # ---------------------------------------------------------
    if not is_question:
        # Negative LIKE first because it represents a correction/removal.
        phrase = _match_first(lower, _LIKE_NEGATIVE)
        if phrase:
            value = _capture_after(lower, phrase)
            if value:
                _remove_like(value, changes)
        else:
            phrase = _match_first(lower, _LIKE_POSITIVE)
            if phrase:
                value = _capture_after(lower, phrase)
                if value:
                    _record_like(value, changes)

        # Negative DISLIKE means the user no longer dislikes something.
        phrase = _match_first(lower, _DISLIKE_NEGATIVE)
        if phrase:
            value = _capture_after(lower, phrase)
            if value:
                _remove_dislike(value, changes)
        else:
            phrase = _match_first(lower, _DISLIKE_POSITIVE)
            if phrase:
                value = _capture_after(lower, phrase)
                if value:
                    _record_dislike(value, changes)

        # Favorite
        phrase = _match_first(lower, _FAVORITE_PATTERNS)
        if phrase:
            value = _capture_after(lower, phrase)
            if value:
                save_fact("favorite", value)
                changes["favorite"] = value

    # ---------------------------------------------------------
    # Mood and events
    # ---------------------------------------------------------
    if not is_question:
        for mood, triggers in _MOOD_TRIGGERS.items():
            if any(trigger in lower for trigger in triggers):
                save_fact("mood", mood)
                changes["mood"] = mood
                break

        for event, triggers in _EVENT_TRIGGERS.items():
            if any(trigger in lower for trigger in triggers):
                save_fact("important_event", event)
                changes["important_event"] = event
                break

    return changes


_ACK_TEMPLATES = {
    "like_added": "Got it — noted you like {}.",
    "like_removed": "Got it — removed {} from your likes.",
    "dislike_added": "Got it — noted you dislike {}.",
    "dislike_removed": "Got it — removed {} from your dislikes.",
    "favorite": "Got it — your favorite is {}.",
    "user_name": "Nice to meet you, {}.",
}


def build_fact_ack(changes: dict):
    for key, template in _ACK_TEMPLATES.items():
        if key in changes:
            return template.format(changes[key])

    return None


# =========================================================
# 🤖 LLM MEMORY FALLBACK
# =========================================================

ALLOWED_KEYS = {
    "user_name",
    "like",
    "favorite",
    "dislike",
    "mood",
    "important_event",
}


def _coerce_to_clean_string(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None

    if isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
        return ", ".join(items) if items else None

    return None


async def ai_extract_memory(text, personality):
    """Use the LLM only when the normal command router already needs it.

    The prompt explicitly asks for CURRENT facts, not questions or guesses.
    """
    prompt = f"""
Extract only CURRENT facts about the user from this message.

Return ONLY a JSON object. No explanation. No markdown.

Allowed keys:
user_name
like
favorite
dislike
mood
important_event

Rules:
- Do not extract facts from questions.
- Do not guess.
- If the user says they no longer like something, do not return it as a like.
- If the user says they hate/dislike something, return it as dislike.
- Values must be short plain strings.
- Omit keys that do not apply.

Message:
{text}

Example:
{{"like": "anime"}}
"""

    response = await ask_ai(prompt, personality, {}, [])

    try:
        data = json.loads(response)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    cleaned = {}

    for key, value in data.items():
        if key not in ALLOWED_KEYS:
            continue

        clean = _coerce_to_clean_string(value)
        if clean:
            cleaned[key] = clean

    return cleaned


# =========================================================
# PUBLIC API
# =========================================================

__all__ = [
    "extract_and_store",
    "build_fact_ack",
    "ai_extract_memory",
]