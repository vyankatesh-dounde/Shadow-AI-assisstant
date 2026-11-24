import asyncio
import unittest
from unittest.mock import patch


class VoiceTTSTest(unittest.TestCase):
    def test_synthesize_generates_sentence_audio_before_demo_fallback(self):
        async def run():
            from core.tts_service import synthesize

            voices = []

            class FakeCommunicate:
                def __init__(self, text, voice, pitch):
                    self.text = text
                    self.voice = voice
                    self.pitch = pitch
                    voices.append(voice)

                async def save(self, filepath):
                    return None

            with patch("core.tts_service.edge_tts.Communicate", FakeCommunicate):
                audio_url = await synthesize("hello shadow")
            self.assertEqual(voices, ["ja-JP-KeitaNeural"])
            self.assertTrue(audio_url.startswith("/static/audio/"))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
