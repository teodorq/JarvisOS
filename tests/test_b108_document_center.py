from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.productivity.document_center import LocalDocumentCenter


class B108DocumentCenterTests(unittest.TestCase):
    def test_demo_scan_and_search(self) -> None:
        with TemporaryDirectory() as temporary:
            service = LocalDocumentCenter(temporary)
            path = service.create_demo()
            result = service.scan(path.parent)
            self.assertEqual(result["scanned"], 1)
            matches = service.search("lokalnego indeksu")
            self.assertEqual(matches[0]["name"], path.name)
            status = service.status()
            self.assertEqual(status["document_count"], 1)
            self.assertFalse(status["remote_indexing"])

    def test_external_path_is_rejected(self) -> None:
        with TemporaryDirectory() as temporary, TemporaryDirectory() as external:
            service = LocalDocumentCenter(temporary)
            with self.assertRaises(ValueError):
                service.scan(external)

    def test_pdf_metadata_is_indexed_without_text_claim(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "AI_PLIKI" / "sample.pdf"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"%PDF-1.4\n")
            service = LocalDocumentCenter(root)
            service.scan(path.parent)
            status = service.status()
            self.assertEqual(status["document_count"], 1)
            self.assertEqual(status["text_document_count"], 0)


if __name__ == "__main__":
    unittest.main()
