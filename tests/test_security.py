import unittest
from collections import deque
from unittest.mock import patch

from server import chat_rate_limited, origin_allowed


class SecurityTest(unittest.TestCase):
    def test_origin_allowlist(self):
        with patch("server.ALLOWED_ORIGINS", ["http://trusted.test"]):
            self.assertTrue(origin_allowed(None))
            self.assertTrue(origin_allowed("http://trusted.test"))
            self.assertFalse(origin_allowed("http://untrusted.test"))

    def test_chat_rate_limit_expires_old_messages(self):
        times = deque()
        with patch("server.CHAT_RATE_LIMIT_MAX_MESSAGES", 2), patch(
            "server.CHAT_RATE_LIMIT_WINDOW_SECONDS", 10
        ):
            self.assertFalse(chat_rate_limited(times, now=100))
            self.assertFalse(chat_rate_limited(times, now=101))
            self.assertTrue(chat_rate_limited(times, now=102))
            self.assertFalse(chat_rate_limited(times, now=111))


if __name__ == "__main__":
    unittest.main()