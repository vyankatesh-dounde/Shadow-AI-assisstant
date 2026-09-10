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

from config import VOICE, VOICE_PITCH, USE_RVC_VOICE

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
    """Generate or return the Shadow voice audio URL for `text`.

    Order of preference:
    1) RVC sentence pipeline if configured and available
    2) Edge TTS sentence generation
    """
    if not text:
        return None

    if USE_RVC_VOICE:
        try:
            from voice.rvc_pipeline import generate_sentence_audio

            generated = await generate_sentence_audio(text)
            if generated:
                return generated
        except Exception as exc:  # pragma: no cover - runtime-dependent path
            print(f"RVC pipeline unavailable: {exc}")

    _cleanup_old_files()

    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = AUDIO_DIR / filename

    try:
        communicate = edge_tts.Communicate(text, VOICE, pitch=VOICE_PITCH)
        await communicate.save(str(filepath))
        return f"/static/audio/{filename}"
    except Exception as exc:  # pragma: no cover - network/runtime-dependent
        print(f"Edge TTS unavailable: {exc}")

    return None
