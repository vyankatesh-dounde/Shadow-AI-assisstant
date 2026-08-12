# core/memory_extractor.py
#
# Two fact-extraction paths:
#   extract_and_store()  - cheap, deterministic, regex-based. Runs on
#                           EVERY message. This is the primary path.
#   ai_extract_memory()  - LLM-based fallback for facts the regexes
#                           miss. Only ever called from brain.py's
#                           Step 4 (the same place ask_ai() itself is
#                           called) - i.e. only on messages that were
#                           ALREADY going to hit the LLM anyway. It
#                           must never run ahead of the command
#                           router, or every reminder/open/volume/etc.
#                           command pays for an Ollama round trip it
#                           doesn't need.
#
# extract_and_store() returns a dict describing what it actually
# changed (e.g. {"like_added": "pizza"}) so callers can react to it -
# specifically brain.py uses this to give a short canned reply for
# plain fact statements ("I like pizza") instead of routing them to
# the LLM, which otherwise rambles about relationship levels and
# invents follow-up questions nobody asked for.

import json

from ai.llm import ask_ai

# =========================================================
# ❤️ LIKE / DISLIKE TRIGGER PHRASES
#
# NOTE: negative phrasing ("i don't like X", "i no longer like X")
# does NOT contain the positive trigger substring ("i like") inside
# it, so a single "is this phrase present, and is it negated"
# approach never actually catches negation - the positive check
# fails first and the message is never recognized as being about
# likes at all. Negative and positive phrases are matched as
# SEPARATE, EXPLICIT pattern lists instead, and negative is checked
# first since it's the more specific case.
# =========================================================

_LIKE_POSITIVE = ["i like", "i love", "i enjoy", "i'm into", "i am into"]
_LIKE_NEGATIVE = [
    "i don't like", "i do not like", "i dont like",
    "i no longer like", "i no longer love", "i no longer enjoy",
    "i'm not into", "i am not into",
]

_DISLIKE_POSITIVE = ["i hate", "i dislike"]
_DISLIKE_NEGATIVE = [
    "i don't hate", "i do not hate", "i dont hate",
    "i don't dislike", "i do not dislike", "i dont dislike",
    "i no longer hate", "i no longer dislike",
]

_FAVORITE_PATTERNS = ["my favorite", "my favourite"]  # both spellings

# =========================================================
# ❓ QUESTION GUARD
#
# A plain substring check for "i hate" / "i like" also matches inside
# QUESTIONS about those facts, not just statements of them - e.g.
# "what do I hate and what do I like" contains the literal substring
# "i hate" ("...do i hate..."), so it used to be captured as a dislike
# declaration whose "value" was the entire rest of the sentence
# ("and what do i like"). That garbage entry is exactly what shows up
# in facts.json today. Recall/question phrasing is filtered out
# before any like/dislike/favorite pattern is checked.
# =========================================================

_QUESTION_STARTERS = (
    "what", "do i", "does", "am i", "is my", "how", "why", "when",
    "which", "who", "can you tell me", "tell me what",
)


def _looks_like_question(lower: str) -> bool:
    stripped = lower.strip()
    if stripped.endswith("?"):
        return True
    return any(stripped.startswith(starter) for starter in _QUESTION_STARTERS)


def _match_first(lower: str, patterns):
    """Return the first pattern from `patterns` found in `lower`, or
    None. Patterns are checked in order, so put longer/more-specific
    phrasing first within a list if it matters."""
    for p in patterns:
        if p in lower:
            return p
    return None


def _capture_after(lower: str, phrase: str) -> str:
    """Grab whatever comes after `phrase` in `lower`, trimmed of
    trailing punctuation/filler ("anymore", "any more", "now") and
    cut off at the first '.', ',' or ' but '."""
    value = lower.split(phrase, 1)[-1].strip()
    value = value.split(".")[0].split(",")[0].split(" but ")[0].strip()

    # strip trailing filler that shows up in removal phrasing -
    # "pizza anymore" / "hiking any more" / "coffee now" should
    # resolve to just the item name
    for filler in (" anymore", " any more", " now"):
        if value.endswith(filler):
            value = value[: -len(filler)].strip()

    return value


_MOOD_TRIGGERS = {
    "stressed": ["i am stressed", "i'm stressed", "i feel stressed"],
    "happy": ["i am happy", "i'm happy", "i feel happy"],
    "sad": ["i am sad", "i'm sad", "i feel sad"],
    "tired": ["i am tired", "i'm tired", "i feel tired"],
    "anxious": ["i am anxious", "i'm anxious", "i feel anxious"],
}

_EVENT_TRIGGERS = {
    "exam": ["exam"],
    "interview": ["interview"],
    "appointment": ["appointment"],
    "deadline": ["deadline"],
}


def extract_and_store(text: str) -> dict:
    """Run every deterministic fact pattern against `text`, persist
    any matches, and return a dict describing what changed. Keys used:
        user_name
        like_added / like_removed
        dislike_added / dislike_removed
        favorite
        mood
        important_event
    Only keys that actually changed are present - an empty dict means
    nothing recognizable was in the message."""
    from core.memory import save_fact, save_fact_list, remove_fact_list  # local import avoids a circular import at module load

    lower = text.lower()
    changes = {}
    is_question = _looks_like_question(lower)

    # 🧑 Name
    if "my name is" in lower:
        name = _capture_after(lower, "my name is")
        if name:
            save_fact("user_name", name.title())
            changes["user_name"] = name.title()

    # ❤️ LIKE / 💔 DISLIKE / ⭐ FAVORITE — skipped entirely for
    # questions/recall phrasing ("what do I like", "do I still hate
    # X?"). Without this guard, "what do I hate and what do I like"
    # gets misread as a dislike statement (see _looks_like_question
    # docstring above) - a question about your facts should never
    # itself change your facts.
    if not is_question:
        # negative phrasing checked first - it's the more specific
        # case, and can never overlap with the positive list since
        # "i don't like" doesn't contain "i like" as a substring, but
        # checking it first keeps the intent obvious.
        neg = _match_first(lower, _LIKE_NEGATIVE)
        if neg:
            value = _capture_after(lower, neg)
            if value:
                removed = remove_fact_list("like", value)
                if removed:
                    changes["like_removed"] = removed
        else:
            pos = _match_first(lower, _LIKE_POSITIVE)
            if pos:
                value = _capture_after(lower, pos)
                if value:
                    save_fact_list("like", value)
                    changes["like_added"] = value

        # 💔 DISLIKE — same shape, mirrored
        neg = _match_first(lower, _DISLIKE_NEGATIVE)
        if neg:
            value = _capture_after(lower, neg)
            if value:
                removed = remove_fact_list("dislike", value)
                if removed:
                    changes["dislike_removed"] = removed
        else:
            pos = _match_first(lower, _DISLIKE_POSITIVE)
            if pos:
                value = _capture_after(lower, pos)
                if value:
                    save_fact_list("dislike", value)
                    changes["dislike_added"] = value

        # ⭐ Favorite
        for phrase in _FAVORITE_PATTERNS:
            if phrase in lower:
                value = _capture_after(lower, phrase)
                if value:
                    save_fact("favorite", value)
                    changes["favorite"] = value
                break

    # 😓 Mood — deliberately NOT given a short canned ack by callers;
    # an emotional disclosure deserves a real (if brief) response, not
    # a clipped "Got it." Mood/event statements ("I am stressed") are
    # rarely phrased as questions, but the same guard is applied for
    # consistency (e.g. "why am i so stressed" shouldn't overwrite mood).
    if not is_question:
        for mood, triggers in _MOOD_TRIGGERS.items():
            if any(t in lower for t in triggers):
                save_fact("mood", mood)
                changes["mood"] = mood
                break

        # 📅 Events — same reasoning as mood, left out of the quick-ack path.
        for event, triggers in _EVENT_TRIGGERS.items():
            if any(t in lower for t in triggers):
                save_fact("important_event", event)
                changes["important_event"] = event
                break

    return changes


# Fields that get a short, canned confirmation instead of an LLM round
# trip. Mood/important_event are intentionally excluded - see notes
# above and in build_fact_ack().
_ACK_TEMPLATES = {
    "like_added": "Got it — noted you like {}.",
    "like_removed": "Got it — removed {} from your likes.",
    "dislike_added": "Got it — noted you dislike {}.",
    "dislike_removed": "Got it — removed {} from your dislikes.",
    "favorite": "Got it — your favorite is {}.",
    "user_name": "Nice to meet you, {}.",
}


def build_fact_ack(changes: dict):
    """Turn an extract_and_store() result into a short one-line reply,
    or None if nothing in `changes` warrants a canned ack (e.g. only
    mood/important_event changed, or changes is empty). Only the
    first matching field is used - a message rarely states more than
    one fact at once, and stacking multiple ack lines would be just
    as noisy as the LLM ramble this replaces."""
    for key, template in _ACK_TEMPLATES.items():
        if key in changes:
            return template.format(changes[key])
    return None


# Keys here MUST match what extract_and_store() above uses, and what
# build_memory_context()/_cmd_memory_recall() in brain.py read back -
# this used to say "name" in the prompt example instead of
# "user_name", so a compliant model saved facts under a key nothing
# else ever looked at.
ALLOWED_KEYS = {"user_name", "like", "favorite", "dislike", "mood", "important_event"}


def _coerce_to_clean_string(value):
    """Turn whatever the model returned for a single key into a clean,
    plain string - or None if there's nothing usable.

    Small local models sometimes return a list for "like"/"dislike"
    (e.g. {"dislike": ["Beatles"]}) instead of a plain string. The old
    code did str(v) on whatever came back, which on a list produces
    the literal text "['Beatles']" - and that's exactly what ends up
    stored verbatim in facts.json. Lists are now flattened into a
    comma-joined string, dicts/numbers/other junk are rejected
    outright, and empty/whitespace-only strings are dropped."""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(items) if items else None

    # Numbers, booleans, dicts, None, etc. aren't valid fact values.
    return None


async def ai_extract_memory(text, personality):
    prompt = f"""
Extract facts about the user from their message, if any are present.

Return ONLY a JSON object - no explanation, no markdown fences, no extra text.

Allowed keys (use only these, omit any that don't apply):
    user_name
    like
    favorite
    dislike
    mood
    important_event

Each value must be a short plain string (not a list, not an object).

Message:
{text}

Example output:
{{"user_name": "John", "like": "python"}}
"""

    response = await ask_ai(prompt, personality, {}, [])

    try:
        data = json.loads(response)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    # Defense in depth: drop anything the model invents that isn't a
    # key the rest of the app actually reads, AND make sure every
    # surviving value is a clean, non-empty string before it's handed
    # back to brain.py for storage.
    cleaned = {}
    for k, v in data.items():
        if k not in ALLOWED_KEYS:
            continue
        value = _coerce_to_clean_string(v)
        if value:
            cleaned[k] = value

    return cleaned