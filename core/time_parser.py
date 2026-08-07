import time
import re
import datetime


def _apply_ampm(hour, ampm):
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return hour


def parse_time(text):
    """Turn a natural-language "when" string into a Unix timestamp.

    Deliberately permissive about wording - the old version required
    an exact "in", "at", or "tomorrow" prefix with no filler words in
    between, so perfectly normal phrasing like "tomorrow at 8am" or
    "remind me in 5 min" silently failed with no useful feedback.
    """
    if not text:
        return None

    text = text.lower().strip()

    # "in 10 minutes" / "in 5 min" / "after 2 hrs" / "in 30 sec"
    match = re.search(r"(?:in|after)\s+(\d+)\s*(second|sec|minute|min|hour|hr)s?\b", text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("sec"):
            return time.time() + amount
        if unit.startswith("min"):
            return time.time() + amount * 60
        if unit.startswith("hr") or unit.startswith("hour"):
            return time.time() + amount * 3600

    # bare "10 minutes" / "30 seconds" / "2 hours" (no leading "in")
    match = re.search(r"^(\d+)\s*(second|sec|minute|min|hour|hr)s?$", text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("sec"):
            return time.time() + amount
        if unit.startswith("min"):
            return time.time() + amount * 60
        return time.time() + amount * 3600

    # "tomorrow at 8am" / "tomorrow 8 am" / "tomorrow at 6:30 pm"
    match = re.search(r"tomorrow(?:\s+at)?\s+(\d{1,2})(?:[:.](\d{2}))?\s?(am|pm)", text)
    if match:
        hour = _apply_ampm(int(match.group(1)), match.group(3))
        minute = int(match.group(2) or 0)
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        target = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target.timestamp()

    if "tomorrow" == text.strip():
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        target = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        return target.timestamp()

    # "noon" / "midnight" (today, or tomorrow if that time already passed)
    if "noon" in text:
        return _next_occurrence(12, 0)
    if "midnight" in text:
        return _next_occurrence(0, 0)

    # "at 6 pm" / "at 6:30pm" / "6pm" / "6:30 pm" (with or without "at")
    match = re.search(r"(?:at\s+)?(\d{1,2})(?:[:.](\d{2}))?\s?(am|pm)", text)
    if match:
        hour = _apply_ampm(int(match.group(1)), match.group(3))
        minute = int(match.group(2) or 0)
        return _next_occurrence(hour, minute)

    # 24-hour clock, e.g. "at 18:30" / "18:30"
    match = re.search(r"(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return _next_occurrence(hour, minute)

    return None


def _next_occurrence(hour, minute):
    """Return the timestamp for today at hour:minute, or tomorrow at
    that time if it's already passed today."""
    now = datetime.datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return target.timestamp()
