# core/reminder_nlp.py
#
# Lets you create a reminder by just saying/typing it in chat, e.g.
# "remind me to drink water in 10 minutes" or "set a reminder to call
# mom at 6pm" - instead of only through the dashboard's manual form.
#
# Before this existed, brain.py had NO handling for this at all, so a
# message like "remind me to drink water" fell straight through to the
# LLM, which just replied with generic advice instead of ever calling
# add_reminder() - the reminder was never actually created.

import re
from datetime import datetime

from core.time_parser import parse_time
from core.reminders import add_reminder

TRIGGER_RE = re.compile(
    r"^(?:please\s+)?(?:"
    r"remind me to|remind me|"
    r"set (?:a |an )?reminder to|set (?:a |an )?reminder|"
    r"add (?:a |an )?reminder to|add (?:a |an )?reminder|"
    r"reminder to"
    r")\s+(.+)$",
    re.I,
)

# Mirrors the phrasing core/time_parser.parse_time understands - used
# here only to find *where* the time phrase sits in the sentence, so
# it can be split off from the actual reminder text.
WHEN_RE = re.compile(
    r"\b("
    r"(?:in|after)\s+\d+\s*(?:second|sec|minute|min|hour|hr)s?"
    r"|tomorrow(?:\s+at)?\s+\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)"
    r"|tomorrow"
    r"|at\s+\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)"
    r"|\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)"
    r"|\d{1,2}:\d{2}"
    r"|noon|midnight"
    r")\b",
    re.I,
)


def try_create_reminder(text: str):
    match = TRIGGER_RE.match(text.strip())
    if not match:
        return None

    body = match.group(1).strip()
    when_match = WHEN_RE.search(body)

    if not when_match:
        return (
            f"What time should I remind you? Try \"remind me to {body} "
            f"in 10 minutes\" or \"...at 6pm\"."
        )

    when_text = when_match.group(0)
    task = (body[: when_match.start()] + body[when_match.end():]).strip()
    task = re.sub(r"^(to|that)\s+", "", task, flags=re.I)   # <-- new: strips leftover "to" when time came first
    task = re.sub(r"\s+", " ", task).strip(" ,.") or "that"

    trigger_time = parse_time(when_text)
    if trigger_time is None:
        return (
            f"I heard \"{when_text}\" but couldn't work out a time from "
            f"it - try phrasing like 'in 10 minutes' or 'at 6pm'."
        )

    add_reminder(task, trigger_time)
    when_str = datetime.fromtimestamp(trigger_time).strftime("%A %I:%M %p")
    return f"Done - I'll remind you to {task} on {when_str}."
