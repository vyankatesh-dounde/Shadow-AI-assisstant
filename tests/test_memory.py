import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.memory import load_preferences, remove_fact_list, save_fact_list
from core.reminders import add_reminder, load_reminders
import memory.storage as storage


class PreferenceMemoryTest(unittest.TestCase):
    def test_reminder_loader_accepts_only_lists(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            with patch("memory.storage.DB_FILE", root / "shadow.db"):
                self.assertEqual(load_reminders(), [])
                add_reminder("test reminder", 1234567890)
                self.assertEqual(len(load_reminders()), 1)

    def test_preference_history_tracks_updates_and_removals(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            with patch("memory.storage.DB_FILE", root / "shadow.db"):
                self.assertEqual(save_fact_list("like", "jazz", "user message"), "jazz")
                self.assertEqual(remove_fact_list("like", "jazz"), "jazz")
                history = load_preferences()["like"]

            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["value"], "jazz")
            self.assertEqual(history[0]["source"], "user message")
            self.assertTrue(history[0]["active"])
            self.assertFalse(history[1]["active"])
            self.assertIn("timestamp", history[1])


if __name__ == "__main__":
    unittest.main()
