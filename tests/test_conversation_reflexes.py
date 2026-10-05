from __future__ import annotations

import pytest

from app.assistant.free_conversation import FreeConversationService


class _NoModel:
    def __init__(self) -> None:
        self.calls = 0

    def reply(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("Common conversation reflex should not call the model")

    @staticmethod
    def status():
        return {"backend": "TEST_LOCAL"}


@pytest.mark.parametrize(
    "message",
    (
        "Jesteś tam?",
        "Kim jesteś?",
        "Czy jesteś człowiekiem?",
        "Czy mogę ci zaufać?",
        "Przepraszam",
        "Nie rozumiem",
        "Potrzebuję wsparcia",
        "Czuję się samotny",
        "Jestem smutny",
        "Jestem zestresowany",
        "Jestem wściekły",
        "Boję się",
        "Jestem zmęczony",
        "Nie mogę zasnąć",
        "Brakuje mi motywacji",
        "Zmotywuj mnie",
        "Pomóż mi się uspokoić",
        "Nudzi mi się",
        "Nie wiem od czego zacząć",
        "Mam dobry humor",
        "Udało mi się",
        "Powiedz coś miłego",
        "Opowiedz żart",
        "Zaproponuj temat rozmowy",
        "Co robisz?",
        "Jak działa twoja pamięć?",
        "Czy umiesz rozmawiać?",
        "Okej",
    ),
)
def test_common_conversation_modes_are_instant(tmp_path, message: str) -> None:
    model = _NoModel()
    service = FreeConversationService(tmp_path, model=model)

    assert service.matches(message) is True
    assert service.reply(message)
    assert model.calls == 0


def test_conversation_reflexes_do_not_capture_computer_commands(tmp_path) -> None:
    service = FreeConversationService(tmp_path, model=_NoModel())

    assert service.matches("Otwórz notatnik") is False
    assert service.matches("Wyłącz komputer") is False
    assert service.matches("Usuń plik") is False
    assert service.status()["instant_reply_modes"] >= 30


def test_specific_identity_question_is_not_shadowed_by_presence(tmp_path) -> None:
    service = FreeConversationService(tmp_path, model=_NoModel())

    assert "programem" in service.reply("Czy jesteś człowiekiem?")
    assert "przejrzystości" in service.reply("Czy mogę ci zaufać?")
