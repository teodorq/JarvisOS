from __future__ import annotations

import shlex
import unittest
from pathlib import Path


class CloudContainerContextTests(unittest.TestCase):
    def test_every_docker_copy_source_exists(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dockerfile = root / "cloud_service" / "Dockerfile"
        sources: list[str] = []
        for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line.startswith("COPY "):
                continue
            tokens = shlex.split(line)
            operands = [token for token in tokens[1:] if not token.startswith("--")]
            self.assertGreaterEqual(len(operands), 2, line)
            sources.extend(operands[:-1])

        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source):
                self.assertNotIn("*", source)
                self.assertTrue((root / source).exists(), source)


if __name__ == "__main__":
    unittest.main()
