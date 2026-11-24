import asyncio
import unittest

from aiortc import RTCPeerConnection, RTCSessionDescription

from integrations.webrtc_audio import (
    QueuedAudioTrack,
    close_audio_session,
    create_audio_session,
)
from server import _speech_segments


class WebRTCAudioTest(unittest.IsolatedAsyncioTestCase):
    async def test_offer_creates_a_connected_audio_session(self):
        client = RTCPeerConnection()
        received_tracks = []
        client.addTransceiver("audio", direction="recvonly")

        @client.on("track")
        def on_track(track):
            received_tracks.append(track)

        offer = await client.createOffer()
        await client.setLocalDescription(offer)

        answer = await create_audio_session({
            "sdp": client.localDescription.sdp,
            "type": client.localDescription.type,
        })
        try:
            await client.setRemoteDescription(
                RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
            )
            self.assertTrue(answer["session_id"])
            self.assertIn("m=audio", answer["sdp"])
            self.assertTrue(received_tracks)
            frame = await asyncio.wait_for(received_tracks[0].recv(), timeout=5)
            self.assertEqual(frame.format.name, "s16")
        finally:
            await client.close()
            await close_audio_session(answer["session_id"])

    async def test_audio_track_emits_queued_pcm_frame(self):
        track = QueuedAudioTrack()
        samples = b"\x01\x00" * 960
        await track.enqueue([samples])

        frame = await track.recv()

        self.assertEqual(frame.format.name, "s16")
        self.assertEqual(frame.samples, 960)
        self.assertEqual(bytes(frame.planes[0]), samples)
        track.stop()

    def test_speech_segments_emit_complete_sentences_and_tail(self):
        segments, remainder = _speech_segments("Hello. Next sentence")
        self.assertEqual(segments, ["Hello."])
        self.assertEqual(remainder, " Next sentence")

        segments, remainder = _speech_segments(remainder, final=True)
        self.assertEqual(segments, ["Next sentence"])
        self.assertEqual(remainder, "")


if __name__ == "__main__":
    unittest.main()
