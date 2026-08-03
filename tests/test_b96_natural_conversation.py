from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService, normalize_user_command


class B96NaturalConversationTests(unittest.TestCase):

    def test_polite_wake_word_is_removed_without_losing_command(self) -> None:
        self.assertEqual(
            normalize_user_command("Jarvis, proszę otwórz Operę"),
            "otwórz Operę",
        )

    def test_repeat_uses_bounded_persistent_context(self) -> None:
        with TemporaryDirectory() as temporary:
            service = NaturalLanguageService(temporary)
            service.context.update(
                command="otwórz notatnik",
                intent="standard",
                target="notatnik",
                response="OK",
            )
            resolved = service.resolve("jeszcze raz")
            self.assertEqual(resolved.resolved, "otwórz notatnik")
            self.assertTrue(resolved.used_context)

    def test_temporal_determiner_does_not_reuse_an_old_target(self) -> None:
        with TemporaryDirectory() as temporary:
            service = NaturalLanguageService(temporary)
            service.context.update(
                command="pokaż test",
                intent="standard",
                target="test B135",
                response="OK",
            )
            temporal = service.resolve("Pokaż mój kalendarz na ten tydzień")
            self.assertEqual(
                temporal.resolved, "Pokaż mój kalendarz na ten tydzień"
            )
            self.assertFalse(temporal.used_context)
            object_reference = service.resolve("Otwórz ten dokument")
            self.assertIn("test B135", object_reference.resolved)
            self.assertTrue(object_reference.used_context)

    def test_context_keeps_only_last_fifty_turns(self) -> None:
        with TemporaryDirectory() as temporary:
            service = NaturalLanguageService(temporary)
            for index in range(70):
                service.context.update(
                    command=f"polecenie {index}",
                    intent="standard",
                )
            self.assertEqual(len(service.context.load()["turns"]), 50)

    def test_status_plan_is_read_only(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan("Pokaż status asystenta")
            self.assertEqual(thought["handler"], "personal_assistant")
            self.assertTrue(thought["read_only"])
            self.assertTrue(thought["can_execute"])

    def test_mutating_memory_command_requires_normal_safety_gate(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan(
                "Zapamiętaj projekt JARVIS OS w C:\\JarvisAI"
            )
            self.assertFalse(thought["read_only"])

    def test_clear_context_does_not_reinsert_the_clear_command(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            controller.handle("Pokaż status asystenta")
            controller.handle("Wyczyść kontekst rozmowy")
            self.assertEqual(
                controller.conversation.context.load()["turns"],
                [],
            )


if __name__ == "__main__":
    unittest.main()
