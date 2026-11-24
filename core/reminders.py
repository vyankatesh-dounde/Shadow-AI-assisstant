import time
import json
import uuid
import re
import datetime
from pathlib import Path
from memory.storage import load_reminders as _db_load, save_reminders as _db_save

BASE_DIR = Path(__file__).resolve().parent.parent
REMINDER_FILE = BASE_DIR / "memory" / "reminders.json"


def load_reminders():
    return _db_load()


def save_reminders(reminders):
    _db_save(reminders)


def add_reminder(text, trigger_time):
    reminders = load_reminders()
    reminders.append({
        "id": f"r_{uuid.uuid4().hex}",
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
        if not isinstance(r, dict):
            continue
        if not r.get("done", False) and isinstance(r.get("time"), (int, float)) and r["time"] <= now:
            r["done"] = True
            if isinstance(r.get("text"), str):
                due.append(r["text"])

    save_reminders(reminders)
    return due


def list_reminders():
    return [r for r in load_reminders() if isinstance(r, dict) and not r.get("done", False)]


def delete_reminder(reminder_id):
    reminders = load_reminders()
    reminders = [r for r in reminders if r.get("id") != reminder_id]
    save_reminders(reminders)


def clear_reminders():
    save_reminders([])


def _apply_ampm(hour, ampm):
    if not 1 <= hour <= 12:
        return None
    return hour + 12 if ampm == "pm" and hour != 12 else (0 if ampm == "am" and hour == 12 else hour)


def _valid_clock(hour, minute):
    return hour is not None and 0 <= hour <= 23 and 0 <= minute <= 59


def _next_occurrence(hour, minute):
    now = datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return target.timestamp()


def parse_time(text):
    if not text:
        return None
    text = text.lower().strip()
    match = re.search(r"(?:in|after)\s+(\d+)\s*(second|sec|minute|min|hour|hr)s?\b", text)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        if unit.startswith("sec"):
            return time.time() + amount
        if unit.startswith("min"):
            return time.time() + amount * 60
        return time.time() + amount * 3600
    match = re.search(r"^(\d+)\s*(second|sec|minute|min|hour|hr)s?$", text)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        if unit.startswith("sec"):
            return time.time() + amount
        if unit.startswith("min"):
            return time.time() + amount * 60
        return time.time() + amount * 3600
    match = re.search(r"tomorrow(?:\s+at)?\s+(\d{1,2})(?:[:.](\d{2}))?\s?(am|pm)", text)
    if match:
        hour = _apply_ampm(int(match.group(1)), match.group(3))
        minute = int(match.group(2) or 0)
        if not _valid_clock(hour, minute):
            return None
        target = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return target.timestamp()
    if text == "tomorrow":
        target = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        return target.timestamp()
    if "noon" in text:
        return _next_occurrence(12, 0)
    if "midnight" in text:
        return _next_occurrence(0, 0)
    match = re.search(r"(?:at\s+)?(\d{1,2})(?:[:.](\d{2}))?\s?(am|pm)", text)
    if match:
        hour = _apply_ampm(int(match.group(1)), match.group(3))
        minute = int(match.group(2) or 0)
        return _next_occurrence(hour, minute) if _valid_clock(hour, minute) else None
    match = re.search(r"(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if match:
        return _next_occurrence(int(match.group(1)), int(match.group(2)))
    return None


TRIGGER_RE = re.compile(
    r"^(?:please\s+)?(?:remind me to|remind me|set (?:a |an )?reminder to|"
    r"set (?:a |an )?reminder|add (?:a |an )?reminder to|add (?:a |an )?reminder|"
    r"reminder to)\s+(.+)$",
    re.I,
)
WHEN_RE = re.compile(
    r"\b((?:in|after)\s+\d+\s*(?:second|sec|minute|min|hour|hr)s?"
    r"|tomorrow(?:\s+at)?\s+\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)"
    r"|tomorrow|at\s+\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)"
    r"|\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)|\d{1,2}:\d{2}|noon|midnight)\b",
    re.I,
)


def try_create_reminder(text: str):
    match = TRIGGER_RE.match(text.strip())
    if not match:
        return None
    body = match.group(1).strip()
    when_match = WHEN_RE.search(body)
    if not when_match:
        return f"What time should I remind you? Try \"remind me to {body} in 10 minutes\"."
    when_text = when_match.group(0)
    task = (body[:when_match.start()] + body[when_match.end():]).strip()
    task = re.sub(r"^(to|that)\s+", "", task, flags=re.I)
    task = re.sub(r"\s+", " ", task).strip(" ,.") or "that"
    trigger_time = parse_time(when_text)
    if trigger_time is None:
        return f"I heard \"{when_text}\" but couldn't work out a time."
    add_reminder(task, trigger_time)
    return f"Done - I'll remind you to {task} on {datetime.datetime.fromtimestamp(trigger_time).strftime('%A %I:%M %p')}."
