from __future__ import annotations

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.natural_actions.understanding import NaturalActionUnderstanding


class _NaturalMail:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.understanding = NaturalActionUnderstanding()

    @staticmethod
    def has_pending() -> bool:
        return False

    @staticmethod
    def matches(command: object) -> bool:
        intent, confidence = NaturalActionUnderstanding.classify(command)
        return intent != "standard" and confidence >= 0.7

    def handle(self, command: object) -> str:
        self.commands.append(str(command))
        return f"Poczta odczytana: {command}"


def test_gmail_followups_switch_safe_read_filters(tmp_path) -> None:
    language = NaturalLanguageService(tmp_path)
    language.context.update(
        command="Pokaż najnowsze maile Gmail",
        intent="gmail_search",
        response="Lista wiadomości.",
    )

    important = language.resolve("A tylko ważne?")
    unread = language.resolve("A nieprzeczytane?")
    latest = language.resolve("A najnowsze?")

    assert important.resolved == "Pokaż ważne maile Gmail"
    assert unread.resolved == "Pokaż nieprzeczytane maile Gmail"
    assert latest.resolved == "Pokaż najnowsze maile Gmail"
    assert all(item.used_context for item in (important, unread, latest))


def test_short_mail_filter_without_gmail_context_is_not_guessed(tmp_path) -> None:
    resolved = NaturalLanguageService(tmp_path).resolve("A tylko ważne?")

    assert resolved.intent == "standard"
    assert resolved.used_context is False


def test_controller_keeps_gmail_topic_across_filter_changes(tmp_path) -> None:
    controller = PersonalAssistantController(tmp_path)
    natural = _NaturalMail()
    controller.natural_actions = natural

    controller.handle("Pokaż najnowsze maile Gmail")
    assert controller.conversation.context.load()["last_intent"] == "gmail_search"

    controller.handle("A tylko ważne?")
    assert natural.commands[-1] == "Pokaż ważne maile Gmail"
    assert controller.conversation.context.load()["last_intent"] == "gmail_search"
