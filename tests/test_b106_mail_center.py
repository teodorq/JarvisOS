from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.productivity.mail_center import LocalMailCenter


class B106MailCenterTests(unittest.TestCase):
    def test_draft_ready_export_and_hash_verification(self) -> None:
        with TemporaryDirectory() as temporary:
            service = LocalMailCenter(temporary)
            draft = service.create_draft("user@example.com", "Raport", "Treść", priority="HIGH")
            self.assertEqual(draft["status"], "DRAFT")
            self.assertEqual(service.mark_ready()["status"], "READY_FOR_EXPORT")
            exported = service.export_ready()
            self.assertTrue(Path(exported["export_path"]).is_file())
            self.assertTrue(service.verify_latest_export())
            status = service.status()
            self.assertEqual(status["exported_count"], 1)
            self.assertFalse(status["remote_delivery"])

    def test_invalid_recipient_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                LocalMailCenter(temporary).create_draft("bad", "Temat", "Treść")

    def test_export_requires_ready_state(self) -> None:
        with TemporaryDirectory() as temporary:
            service = LocalMailCenter(temporary)
            service.create_draft("user@example.com", "Raport", "Treść")
            with self.assertRaises(ValueError):
                service.export_ready()


if __name__ == "__main__":
    unittest.main()
