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


def save_fact(key, value):
    facts = load_facts()
    facts[key] = value
    FACTS_FILE.write_text(json.dumps(facts, indent=2))
