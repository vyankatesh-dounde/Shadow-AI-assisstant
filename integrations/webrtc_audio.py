import asyncio
import io
import uuid
from fractions import Fraction

import av
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import AudioStreamTrack, MediaStreamError

from config import USE_RVC_VOICE, VOICE, VOICE_PITCH
import edge_tts

AUDIO_RATE = 48_000
FRAME_SAMPLES = 960
FRAME_BYTES = FRAME_SAMPLES * 2
_sessions: dict[str, tuple[RTCPeerConnection, "QueuedAudioTrack"]] = {}


class QueuedAudioTrack(AudioStreamTrack):
    def __init__(self):
        super().__init__()
        self.frames: asyncio.Queue[bytes] = asyncio.Queue(maxsize=500)
        self.finished = False
        self._pts = 0

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError

        try:
            data = await asyncio.wait_for(self.frames.get(), timeout=0.1)
        except asyncio.TimeoutError:
            if self.finished and self.frames.empty():
                self.stop()
                raise MediaStreamError
            data = bytes(FRAME_BYTES)

        frame = av.AudioFrame(format="s16", layout="mono", samples=FRAME_SAMPLES)
        frame.planes[0].update(data[:FRAME_BYTES].ljust(FRAME_BYTES, b"\0"))
        frame.sample_rate = AUDIO_RATE
        frame.pts = self._pts
        frame.time_base = Fraction(1, AUDIO_RATE)
        self._pts += FRAME_SAMPLES
        return frame

    async def enqueue(self, frames: list[bytes]):
        for frame in frames:
            await self.frames.put(frame)

    def finish(self):
        self.finished = True


async def create_audio_session(offer: dict) -> dict:
    if not isinstance(offer, dict):
        raise ValueError("A valid WebRTC offer is required.")
    sdp = offer.get("sdp")
    description_type = offer.get("type")
    if not isinstance(sdp, str) or description_type != "offer":
        raise ValueError("A valid WebRTC offer is required.")

    peer = RTCPeerConnection()
    track = QueuedAudioTrack()
    peer.addTrack(track)
    try:
        await peer.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type=description_type)
        )
        answer = await peer.createAnswer()
        await peer.setLocalDescription(answer)
    except Exception:
        await peer.close()
        raise

    session_id = uuid.uuid4().hex
    _sessions[session_id] = (peer, track)

    @peer.on("connectionstatechange")
    async def on_connection_state_change():
        if peer.connectionState in {"failed", "closed"}:
            _sessions.pop(session_id, None)
            track.stop()

    return {
        "session_id": session_id,
        "sdp": peer.localDescription.sdp,
        "type": peer.localDescription.type,
    }


async def stream_tts_to_session(session_id: str, text: str) -> bool:
    if USE_RVC_VOICE:
        return False
    session = _sessions.get(session_id)
    if session is None:
        return False

    _, track = session
    communicate = edge_tts.Communicate(text, VOICE, pitch=VOICE_PITCH)
    mp3 = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            mp3.extend(chunk["data"])
    if not mp3:
        return False

    frames = await asyncio.to_thread(_decode_mp3, bytes(mp3))
    if not frames:
        return False
    await track.enqueue(frames)
    return True


def _decode_mp3(data: bytes) -> list[bytes]:
    pcm = bytearray()
    with av.open(io.BytesIO(data), format="mp3") as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=AUDIO_RATE)
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                pcm.extend(converted.to_ndarray().tobytes())
        for converted in resampler.resample(None):
            pcm.extend(converted.to_ndarray().tobytes())

    return [
        bytes(pcm[offset:offset + FRAME_BYTES]).ljust(FRAME_BYTES, b"\0")
        for offset in range(0, len(pcm), FRAME_BYTES)
    ]


def finish_audio_session(session_id: str) -> None:
    session = _sessions.get(session_id)
    if session is not None:
        session[1].finish()


async def close_audio_session(session_id: str) -> None:
    session = _sessions.pop(session_id, None)
    if session is None:
        return
    peer, track = session
    track.stop()
    await peer.close()


async def close_all_audio_sessions() -> None:
    for session_id in tuple(_sessions):
        await close_audio_session(session_id)
