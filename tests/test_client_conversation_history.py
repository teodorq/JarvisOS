from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.gui.client_conversation_history import ClientConversationHistory
from app.gui.client_result_formatter import ClientResultCard


class ClientConversationHistoryTests(unittest.TestCase):
    def test_restores_only_last_eight_messages_with_cards(self) -> None:
        with TemporaryDirectory() as directory:
            history = ClientConversationHistory(Path(directory))
            card = ClientResultCard(
                "general", "JARVIS", "Gotowe", "Gotowe", "Gotowe"
            )
            messages = [
                ("Ty" if index % 2 == 0 else "JARVIS", f"tekst {index}",
                 None if index % 2 == 0 else card)
                for index in range(10)
            ]

            history.save(messages)
            restored = history.load()

            self.assertEqual(len(restored), 8)
            self.assertEqual(restored[0][1], "tekst 2")
            self.assertEqual(restored[-1][1], "tekst 9")
            self.assertIsNotNone(restored[-1][2])

    def test_masks_credentials_before_writing_to_disk(self) -> None:
        with TemporaryDirectory() as directory:
            history = ClientConversationHistory(Path(directory))
            history.save([
                ("Ty", "token: abc123456 hasło jest super-secret", None),
                ("JARVIS", "Bearer eyJhbGciOiJIUzI1NiJ9.payload", None),
            ])

            raw = history.store.path.read_text(encoding="utf-8")

            self.assertNotIn("abc123456", raw)
            self.assertNotIn("super-secret", raw)
            self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", raw)
            self.assertIn("UKRYTO", raw)

    def test_clear_removes_visible_history_payload(self) -> None:
        with TemporaryDirectory() as directory:
            history = ClientConversationHistory(Path(directory))
            history.save([("Ty", "sprawdź status", None)])

            history.clear()

            self.assertEqual(history.load(), [])

    def test_ignores_invalid_entries_from_damaged_shape(self) -> None:
        with TemporaryDirectory() as directory:
            history = ClientConversationHistory(Path(directory))
            history.store.save({
                "messages": [None, {"author": "intruz", "text": "x"}],
            })

            self.assertEqual(history.load(), [])


if __name__ == "__main__":
    unittest.main()
