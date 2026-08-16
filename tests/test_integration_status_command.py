from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.client_tool_drawer import SAFE_CLIENT_ACTIONS
from app.integrations import IntegrationStatusService


class IntegrationStatusServiceTests(unittest.TestCase):
    def test_default_status_is_local_disabled_and_secret_free(self) -> None:
        service = IntegrationStatusService({})

        status = service.status()
        rendered = service.format_status()

        self.assertEqual(status["voice"]["selected"], "LOCAL")
        self.assertTrue(status["voice"]["configured"])
        self.assertFalse(status["azure"]["planner_configured"])
        self.assertTrue(all(
            not provider["enabled"]
            for provider in status["external"].values()
        ))
        self.assertFalse(status["network_checked"])
        self.assertFalse(status["secrets_exposed"])
        self.assertIn("bez zewnętrznych opłat", rendered)
        self.assertIn("RevenueCat: wyłączony", rendered)
        self.assertIn("nie wykonano połączeń", rendered)

    def test_configured_status_never_contains_secrets_or_private_urls(self) -> None:
        environment = {
            "JARVIS_OS_VOICE_PROVIDER": "CARTESIA",
            "CARTESIA_API_KEY": "voice-super-secret",
            "CARTESIA_VOICE_ID": "voice_123",
            "JARVIS_OS_CLOUD_URL": "https://planner.private.example/v1/plan",
            "JARVIS_OS_CLOUD_API_TOKEN": "azure-super-secret",
            "JARVIS_OS_REMOTE_QUEUE_URL": "https://private.queue.core.windows.net/commands",
            "JARVIS_OS_REVENUECAT_MCP_ENABLED": "true",
            "JARVIS_OS_REVENUECAT_MCP_TOKEN": "revenue-super-secret",
            "JARVIS_OS_META_ADS_MCP_ENABLED": "true",
            "JARVIS_OS_META_ADS_MCP_URL": "https://meta-connector.example/mcp",
            "JARVIS_OS_META_ADS_MCP_ALLOWED_HOSTS": "meta-connector.example",
            "JARVIS_OS_META_ADS_MCP_ACCESS_TOKEN": "meta-super-secret",
            "JARVIS_OS_CLAUDE_ENABLED": "true",
            "JARVIS_OS_CLAUDE_MODEL": "claude-sonnet-test",
            "ANTHROPIC_API_KEY": "claude-super-secret",
        }
        service = IntegrationStatusService(environment)

        status = service.status()
        rendered = service.format_status()

        self.assertTrue(status["voice"]["configured"])
        self.assertTrue(status["azure"]["planner_configured"])
        self.assertTrue(status["azure"]["phone_queue_configured"])
        self.assertTrue(all(
            provider["ready"] for provider in status["external"].values()
        ))
        self.assertNotIn("endpoint_host", repr(status))
        self.assertNotIn("model", repr(status))
        for forbidden in (
            "voice-super-secret",
            "azure-super-secret",
            "revenue-super-secret",
            "meta-super-secret",
            "claude-super-secret",
            "planner.private.example",
            "meta-connector.example",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, rendered)
                self.assertNotIn(forbidden, repr(status))
        self.assertIn("Cartesia — skonfigurowany", rendered)
        self.assertIn("Claude: skonfigurowany", rendered)


class IntegrationStatusCommandTests(unittest.TestCase):
    def test_natural_variants_route_to_read_only_personal_assistant(self) -> None:
        for command in (
            "Pokaż status integracji",
            "Jakie integracje mam?",
            "Status Claude",
            "Połączenia zewnętrzne",
        ):
            with self.subTest(command=command):
                self.assertEqual(
                    NaturalLanguageService.classify(command), "integration_status"
                )
                self.assertTrue(PersonalAssistantController.matches(command))

        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(Path(directory))
            thought = controller.plan("Pokaż status integracji")
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertEqual(thought["assistant_intent"], "integration_status")
            self.assertTrue(thought["read_only"])

    def test_command_uses_local_snapshot_and_does_not_leak_secret(self) -> None:
        environment = {
            "JARVIS_OS_REVENUECAT_MCP_ENABLED": "true",
            "JARVIS_OS_REVENUECAT_MCP_TOKEN": "never-print-this-secret",
        }
        with TemporaryDirectory() as directory, patch.dict(
            os.environ, environment, clear=False
        ):
            controller = PersonalAssistantController(Path(directory))
            response = controller.handle("Pokaż status integracji")

        self.assertIn("Integracje JARVIS OS", response)
        self.assertIn("RevenueCat: skonfigurowany", response)
        self.assertNotIn("never-print-this-secret", response)

    def test_client_drawer_exposes_safe_integration_shortcut(self) -> None:
        action = next(
            action
            for _group, actions in SAFE_CLIENT_ACTIONS
            for action in actions
            if action.label == "INTEGRACJE"
        )
        self.assertEqual(action.command, "Pokaż status integracji")
        self.assertFalse(action.guided)
        self.assertEqual(ClientCapabilityPolicy.denial_message(action.command), "")


if __name__ == "__main__":
    unittest.main()
