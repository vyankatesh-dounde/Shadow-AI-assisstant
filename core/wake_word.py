# core/wake_word.py
#
# A bare "shadow" / "hey shadow" utterance is the WAKE WORD - it's
# what opens the mic, not an actual question. Before this file
# existed, brain.py had no idea what to do with that bare word, so it
# fell straight through every command check and landed on the LLM,
# which then invented a generic reply ("Hello! I hope your day is
# going well...") instead of just acknowledging you. That round trip
# also meant a multi-second wait for something that should be instant.
#
# This module is checked FIRST, before anything else in brain.py -
# before command matching, before memory learning, before the LLM.
# If it matches, the wake word is swallowed here and NEVER passed on.

import json
import random
import datetime
from pathlib import Path

from config import WAKE_WORDS

BASE_DIR = Path(__file__).resolve().parent.parent
WAKE_STATE_FILE = BASE_DIR / "memory" / "wake_state.json"

# Short, instant acknowledgments for every wake-up after the first
# one today (mirrors what the browser's local speech synthesis says
# client-side per the README, kept here too as a server-side
# guarantee that a wake word can never reach the LLM even if the
# client-side handling is bypassed, e.g. typed instead of spoken).
ACKNOWLEDGMENTS = ["Yes?", "Go ahead.", "I'm listening.", "What do you need?"]


def is_wake_word(text: str) -> bool:
    """True if `text` is NOTHING BUT a wake word (allowing for a
    trailing punctuation mark) - i.e. "shadow" or "hey shadow" and
    nothing else. A command that merely CONTAINS the word, like
    "shadow, open chrome", is not a wake word and should be handled
    normally by the command router."""
    stripped = text.strip().lower().rstrip("!?.")
    return stripped in WAKE_WORDS


def _load_state():
    if WAKE_STATE_FILE.exists():
        try:
            return json.loads(WAKE_STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_state(state):
    WAKE_STATE_FILE.parent.mkdir(exist_ok=True)
    WAKE_STATE_FILE.write_text(json.dumps(state, indent=2))


def handle_wake_word(text: str) -> str:
    """Return the greeting/acknowledgment for a bare wake-word
    utterance. Once per day you get a proper "Good morning/afternoon/
    evening. How can I help?"; every other time today it's a short
    "Yes?" style nudge. This function is pure canned text - it never
    calls the LLM."""
    state = _load_state()
    today = datetime.date.today().isoformat()

    if state.get("last_greeted_date") != today:
        state["last_greeted_date"] = today
        _save_state(state)

        hour = datetime.datetime.now().hour
        if hour < 12:
            part = "morning"
        elif hour < 18:
            part = "afternoon"
        else:
            part = "evening"
        return f"Good {part}. How can I help?"

    return random.choice(ACKNOWLEDGMENTS)
