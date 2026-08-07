# integrations/daily_memory.py

import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"

DAILY_FILE = MEMORY_DIR / "daily_memory.json"


def save_daily_summary(conversation):
    if not conversation:
        return

    summary = "We talked about " + ", ".join(
        [msg["content"][:25] for msg in conversation if msg["role"] == "user"]
    )

    data = {
        "last_summary": summary,
        "timestamp": time.time()
    }

    MEMORY_DIR.mkdir(exist_ok=True)
    DAILY_FILE.write_text(json.dumps(data, indent=2))


def load_daily_summary():
    if DAILY_FILE.exists():
        try:
            return json.loads(DAILY_FILE.read_text())
        except:
            return None
    return None
