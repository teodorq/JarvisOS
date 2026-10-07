from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.assistant.controller import PersonalAssistantController
from app.assistant.free_conversation import FreeConversationService
from app.assistant.natural_language import NaturalLanguageService, normalize_user_command


class _Model:
    @staticmethod
    def reply(_messages, *, system):
        return "Porozmawiajmy spokojnie."

    @staticmethod
    def status():
        return {"backend": "TEST_LOCAL"}


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
            conversation = FreeConversationService(temporary, model=_Model())
            conversation.reply("Porozmawiajmy o planach")
            controller.handle("Pokaż status asystenta")
            response = controller.handle("Wyczyść historię rozmowy")
            self.assertEqual(
                controller.conversation.context.load()["turns"],
                [],
            )
            self.assertEqual(conversation.status()["turn_count"], 0)
            self.assertIn("historię rozmowy", response)

    def test_user_controls_personal_conversation_memory(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            remember = controller.plan("Zapamiętaj, że lubię kawę")
            self.assertEqual(remember["assistant_intent"], "remember_personal_fact")
            self.assertFalse(remember["read_only"])
            self.assertIn(
                "lubię kawę",
                controller.handle("Zapamiętaj, że lubię kawę").casefold(),
            )

            listing = controller.plan("Co o mnie pamiętasz?")
            self.assertTrue(listing["read_only"])
            self.assertIn("Lubię kawę", controller.handle("Co o mnie pamiętasz?"))
            self.assertIn("Zapomniałem", controller.handle("Zapomnij o kawie"))
            self.assertIn("Nie mam jeszcze", controller.handle("Co o mnie pamiętasz?"))

    def test_sensitive_fact_is_not_saved(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            answer = controller.handle("Zapamiętaj, że hasło to sekret123")
            self.assertIn("Nie zapiszę", answer)
            self.assertEqual(
                controller.projects.list_preferences(category="personal_fact"), []
            )

    def test_conversation_style_is_persistent_and_user_controlled(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            change = controller.plan("Mów krócej")
            self.assertEqual(change["assistant_intent"], "conversation_style")
            self.assertFalse(change["read_only"])
            self.assertIn("krótki", controller.handle("Mów krócej"))

            status = controller.plan("Jaki jest tryb rozmowy?")
            self.assertTrue(status["read_only"])
            self.assertIn("krótki", controller.handle("Jaki jest tryb rozmowy?"))
            reloaded = PersonalAssistantController(temporary)
            self.assertEqual(
                reloaded.projects.get_preference("conversation_style"),
                "concise",
            )

    def test_conversation_options_are_available_as_a_read_only_command(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)
            thought = controller.plan("Pokaż opcje rozmowy")

            self.assertTrue(thought["read_only"])
            answer = controller.handle("Pokaż opcje rozmowy")
            self.assertIn("mów dokładniej", answer)
            self.assertIn("rozmawiaj luźniej", answer)

    def test_natural_conversation_style_can_be_restored(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = PersonalAssistantController(temporary)

            self.assertIn("naturalny", controller.handle("Rozmawiaj naturalnie"))
            self.assertEqual(
                controller.projects.get_preference("conversation_style"),
                "natural",
            )


if __name__ == "__main__":
    unittest.main()
