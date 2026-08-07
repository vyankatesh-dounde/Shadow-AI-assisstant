import time
import json
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
        "id": f"r_{int(time.time() * 1000)}",
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
        if not r["done"] and r["time"] <= now:
            r["done"] = True
            due.append(r["text"])

    save_reminders(reminders)
    return due


def list_reminders():
    return [r for r in load_reminders() if not r["done"]]


def delete_reminder(reminder_id):
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)


def clear_reminders():
    save_reminders([])
