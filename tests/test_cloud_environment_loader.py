from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.cloud.environment import load_cloud_environment


class CloudEnvironmentLoaderTests(unittest.TestCase):
    def _write(self, root: str, content: str) -> None:
        config = Path(root) / "config"
        config.mkdir(parents=True)
        (config / "cloud.env").write_text(content, encoding="utf-8")

    def test_loads_only_allowed_cloud_values(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            self._write(
                root,
                "# local only\n"
                "JARVIS_OS_CLOUD_URL=https://cloud.example\n"
                "JARVIS_OS_CLOUD_API_TOKEN='token-with=padding'\n"
                "UNRELATED_SECRET=must-not-load\n",
            )
            with patch.dict(os.environ, {}, clear=True):
                loaded = load_cloud_environment(root)
                self.assertEqual(
                    loaded,
                    (
                        "JARVIS_OS_CLOUD_URL",
                        "JARVIS_OS_CLOUD_API_TOKEN",
                    ),
                )
                self.assertEqual(
                    os.environ["JARVIS_OS_CLOUD_API_TOKEN"],
                    "token-with=padding",
                )
                self.assertNotIn("UNRELATED_SECRET", os.environ)

    def test_existing_environment_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "JARVIS_OS_CLOUD_API_TOKEN=file-token\n")
            with patch.dict(
                os.environ,
                {"JARVIS_OS_CLOUD_API_TOKEN": "environment-token"},
                clear=True,
            ):
                self.assertEqual(load_cloud_environment(root), ())
                self.assertEqual(
                    os.environ["JARVIS_OS_CLOUD_API_TOKEN"],
                    "environment-token",
                )
