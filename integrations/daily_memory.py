# integrations/daily_memory.py

import json
import time
<<<<<<< HEAD
from datetime import date, datetime
=======
>>>>>>> e5723e5c72817929ddcb45caa8d594873b1c6552
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

<<<<<<< HEAD
    data = _load_all()
    data[date.today().isoformat()] = {
        "summary": summary,
        "timestamp": time.time(),
    }

    MEMORY_DIR.mkdir(exist_ok=True)
    DAILY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_all():
    if DAILY_FILE.exists():
        try:
            data = json.loads(DAILY_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {}
            # Migrate the old single-summary shape without losing it.
            if "last_summary" in data:
                timestamp = data.get("timestamp", time.time())
                day = datetime.fromtimestamp(timestamp).date().isoformat()
                return {day: {"summary": data["last_summary"], "timestamp": timestamp}}
            return data
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}
    return {}


def load_daily_summary(day=None):
    """Return one calendar day's summary, defaulting to today."""
    record = _load_all().get(day or date.today().isoformat())
    return record if isinstance(record, dict) else None
=======
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
>>>>>>> e5723e5c72817929ddcb45caa8d594873b1c6552
