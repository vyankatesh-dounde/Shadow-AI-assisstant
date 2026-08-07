# core/tts_service.py
#
# Web-friendly text-to-speech. Instead of playing audio through the
# server's own speakers (core/speaker.py did that for the old desktop
# loop), this renders an mp3 into static/audio/ and hands back a URL
# that ANY connected browser (phone, tablet, laptop) can play.

import time
import uuid
from pathlib import Path

import edge_tts

from config import VOICE, VOICE_PITCH

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MAX_AGE_SECONDS = 600  # delete generated clips older than 10 minutes


def _cleanup_old_files():
    now = time.time()
    for f in AUDIO_DIR.glob("*.mp3"):
        try:
            if now - f.stat().st_mtime > MAX_AGE_SECONDS:
                f.unlink()
        except Exception:
            pass


async def synthesize(text: str) -> str:
    """Generate speech audio for `text`, return a URL path (e.g.
    /static/audio/<id>.mp3) the frontend can drop straight into an
    <audio> tag."""
    if not text:
        return None

    _cleanup_old_files()

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = AUDIO_DIR / filename

    communicate = edge_tts.Communicate(text, VOICE, pitch=VOICE_PITCH)
    await communicate.save(str(filepath))

    return f"/static/audio/{filename}"
