import asyncio
import unittest


class VoiceTTSTest(unittest.TestCase):
    def test_synthesize_generates_sentence_audio_before_demo_fallback(self):
        async def run():
            from core.tts_service import synthesize
            audio_url = await synthesize("hello shadow")
            self.assertTrue(audio_url.startswith("/static/audio/"))

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
