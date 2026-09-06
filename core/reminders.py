import time
import json
<<<<<<< HEAD
import uuid
=======
>>>>>>> e5723e5c72817929ddcb45caa8d594873b1c6552
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REMINDER_FILE = BASE_DIR / "memory" / "reminders.json"


def load_reminders():
    if REMINDER_FILE.exists():
        try:
            return json.loads(REMINDER_FILE.read_text())
        except:
            return []
    return []


def save_reminders(reminders):
    REMINDER_FILE.parent.mkdir(exist_ok=True)
    REMINDER_FILE.write_text(json.dumps(reminders, indent=2))


def add_reminder(text, trigger_time):
    reminders = load_reminders()
    reminders.append({
<<<<<<< HEAD
        "id": f"r_{uuid.uuid4().hex}",
=======
        "id": f"r_{int(time.time() * 1000)}",
>>>>>>> e5723e5c72817929ddcb45caa8d594873b1c6552
        "text": text,
        "time": trigger_time,
        "done": False
    })
    save_reminders(reminders)


def get_due_reminders():
    now = time.time()
    reminders = load_reminders()

    due = []
    for r in reminders:
<<<<<<< HEAD
        if not isinstance(r, dict):
            continue
        if not r.get("done", False) and isinstance(r.get("time"), (int, float)) and r["time"] <= now:
            r["done"] = True
            if isinstance(r.get("text"), str):
                due.append(r["text"])
=======
        if not r["done"] and r["time"] <= now:
            r["done"] = True
            due.append(r["text"])
>>>>>>> e5723e5c72817929ddcb45caa8d594873b1c6552

    save_reminders(reminders)
    return due


def list_reminders():
<<<<<<< HEAD
    return [r for r in load_reminders() if isinstance(r, dict) and not r.get("done", False)]
=======
    return [r for r in load_reminders() if not r["done"]]
>>>>>>> e5723e5c72817929ddcb45caa8d594873b1c6552


def delete_reminder(reminder_id):
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)


def clear_reminders():
    save_reminders([])
