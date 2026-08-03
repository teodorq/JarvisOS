from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.cloud.client import CloudPlannerSettings
from cloud_service.main import ServiceConfig


class CloudEnvironmentTests(unittest.TestCase):
    def test_jarvis_os_names_take_precedence(self) -> None:
        values = {
            "JARVIS_OS_CLOUD_URL": "https://new.example/",
            "JARVIS_OS_CLOUD_API_TOKEN": "new-token",
            "JARVIS_OS_CLOUD_TIMEOUT_SECONDS": "7",
            "JARVIS_CLOUD_URL": "https://legacy.example",
            "JARVIS_CLOUD_API_TOKEN": "legacy-token",
            "JARVIS_CLOUD_TIMEOUT_SECONDS": "60",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = CloudPlannerSettings.from_environment()
            service = ServiceConfig.from_environment()
        self.assertEqual(settings.base_url, "https://new.example")
        self.assertEqual(settings.api_token, "new-token")
        self.assertEqual(settings.timeout_seconds, 7.0)
        self.assertEqual(service.api_token, "new-token")

    def test_legacy_names_remain_compatible(self) -> None:
        values = {
            "JARVIS_CLOUD_URL": "https://legacy.example/",
            "JARVIS_CLOUD_API_TOKEN": "legacy-token",
            "JARVIS_CLOUD_TIMEOUT_SECONDS": "9",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = CloudPlannerSettings.from_environment()
            service = ServiceConfig.from_environment()
        self.assertEqual(settings.base_url, "https://legacy.example")
        self.assertEqual(settings.api_token, "legacy-token")
        self.assertEqual(settings.timeout_seconds, 9.0)
        self.assertEqual(service.api_token, "legacy-token")


if __name__ == "__main__":
    unittest.main()
