from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.assistant.capability_guide import CapabilityGuideService
from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.client_tool_drawer import SAFE_CLIENT_ACTIONS


class CapabilityGuideServiceTests(unittest.TestCase):
    def test_guide_contains_verified_daily_categories_and_no_owner_tools(self) -> None:
        guide = CapabilityGuideService()

        status = guide.status()
        rendered = guide.format_guide()

        self.assertEqual(status["category_count"], 6)
        self.assertEqual(status["example_count"], 12)
        self.assertTrue(status["client_safe"])
        self.assertFalse(status["external_requests"])
        for title in (
            "Twój dzień",
            "Poczta i kalendarz",
            "Dokumenty i pamięć",
            "Komputer i głos",
            "Pogoda",
            "System i integracje",
        ):
            with self.subTest(title=title):
                self.assertIn(title, rendered)
        for owner_only in ("AutoDev", "trading", "reklamy", "zmień kod"):
            with self.subTest(owner_only=owner_only):
                self.assertNotIn(owner_only, rendered)
        self.assertNotIn("B96", rendered)

    def test_every_advertised_example_is_routed_and_client_safe(self) -> None:
        examples = CapabilityGuideService().examples()
        self.assertEqual(len(examples), len(set(examples)))
        for command in examples:
            with self.subTest(command=command):
                self.assertTrue(PersonalAssistantController.matches(command))
                self.assertEqual(ClientCapabilityPolicy.denial_message(command), "")


class CapabilityGuideCommandTests(unittest.TestCase):
    def test_natural_help_variants_are_read_only(self) -> None:
        variants = (
            "Co potrafisz?",
            "Co możesz zrobić?",
            "Jakie masz funkcje?",
            "Pokaż pomoc",
            "Jak z ciebie korzystać?",
            "Lista poleceń",
        )
        for command in variants:
            with self.subTest(command=command):
                self.assertEqual(
                    NaturalLanguageService.classify(command), "capability_help"
                )
                self.assertTrue(PersonalAssistantController.matches(command))

        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(Path(directory))
            thought = controller.plan("Co potrafisz?")
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertEqual(thought["assistant_intent"], "capability_help")
            self.assertTrue(thought["read_only"])

    def test_command_returns_human_guide_without_running_an_action(self) -> None:
        with TemporaryDirectory() as directory:
            controller = PersonalAssistantController(Path(directory))
            response = controller.handle("Co potrafisz?")

        self.assertIn("JARVIS OS — w czym mogę Ci pomóc", response)
        self.assertIn("Co jest teraz najważniejsze?", response)
        self.assertIn("Pokaż status integracji", response)
        self.assertIn("wymagają potwierdzenia", response)

    def test_client_drawer_has_direct_help_shortcut(self) -> None:
        action = next(
            action
            for _group, actions in SAFE_CLIENT_ACTIONS
            for action in actions
            if action.label == "CO POTRAFIĘ"
        )
        self.assertEqual(action.command, "Co potrafisz?")
        self.assertFalse(action.guided)
        self.assertEqual(ClientCapabilityPolicy.denial_message(action.command), "")


if __name__ == "__main__":
    unittest.main()
