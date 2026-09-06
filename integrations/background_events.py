"""Connection-layer background tasks that publish function-layer state."""

import asyncio

from config import REMINDER_POLL_INTERVAL, STATUS_BROADCAST_INTERVAL
from core.reminders import get_due_reminders, list_reminders
from core.system_status import get_status
from core.tts_service import synthesize


async def watch_reminders(manager):
    while True:
        try:
            due = get_due_reminders()
            for text in due:
                audio_url = None
                try:
                    audio_url = await synthesize(f"Reminder: {text}")
                except Exception as error:
                    print("TTS error:", error)
                await manager.broadcast({"type": "reminder_due", "text": text, "audio_url": audio_url})
            if due:
                await manager.broadcast({"type": "reminders_updated", "reminders": list_reminders()})
        except Exception as error:
            print("Reminder watcher error:", error)
        await asyncio.sleep(REMINDER_POLL_INTERVAL)


async def broadcast_status(manager):
    while True:
        try:
            if manager.active:
                await manager.broadcast({"type": "status", **get_status()})
        except Exception as error:
            print("Status broadcaster error:", error)
        await asyncio.sleep(STATUS_BROADCAST_INTERVAL)
