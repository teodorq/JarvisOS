from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.ai.client_brain import ClientBrain
from app.assistant.free_conversation import FreeConversationService
from app.assistant.project_memory import ProjectMemoryService


class _Model:
    def __init__(self, answers: list[str] | None = None) -> None:
        self.answers = list(answers or ["To jest naturalna odpowiedź."])
        self.calls: list[tuple[list[dict[str, str]], str]] = []

    def reply(self, messages, *, system):
        self.calls.append((list(messages), system))
        return self.answers.pop(0)

    @staticmethod
    def status():
        return {"backend": "TEST_LOCAL", "remote": False, "tools": False}


class _StandardAssistant:
    @staticmethod
    def resolve_command(command: str):
        return SimpleNamespace(intent="standard", resolved=command)

    @staticmethod
    def matches(_command: object) -> bool:
        return False


def test_conversation_matches_questions_but_not_computer_commands(tmp_path) -> None:
    service = FreeConversationService(tmp_path, model=_Model())

    assert service.matches("Co myślisz o sztucznej inteligencji?") is True
    assert service.matches("Dzisiaj było mi ciężko") is True
    assert service.matches("Cześć JARVIS") is True
    assert service.matches("Ostatnio dużo o tym myślę") is True
    assert service.matches("Lubię wieczorne spacery") is True
    assert service.matches("Moim zdaniem to dobry pomysł") is True
    assert service.matches("Otwórz notatnik") is False
    assert service.matches("Wyłącz komputer") is False

    service.reply("Porozmawiajmy o planach")
    assert service.matches("Napisz maila do Ani") is False
    assert service.matches("Rozwijaj JARVIS dalej") is False


def test_local_model_uses_bounded_cpu_profile(monkeypatch) -> None:
    from app.assistant.local_chat_model import LocalChatModel

    monkeypatch.setenv("JARVIS_OS_CHAT_CPU_THREADS", "200")
    monkeypatch.setenv("JARVIS_OS_CHAT_GPU_LAYERS", "0")
    model = LocalChatModel()

    assert model.cpu_threads == 16
    assert model.gpu_layers == 0
    assert model.timeout == 30.0
    assert model.status()["processor"] == "CPU"


def test_local_model_sends_no_tools_to_local_ollama(monkeypatch) -> None:
    from app.assistant import local_chat_model

    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def read(_limit):
            return json.dumps({"message": {"content": "Jasne, porozmawiajmy."}}).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(local_chat_model.urllib.request, "urlopen", fake_urlopen)
    model = local_chat_model.LocalChatModel()
    answer = model.reply([{"role": "user", "content": "Cześć"}], system="test")

    assert answer == "Jasne, porozmawiajmy."
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["payload"]["model"] == "gemma3:4b"
    assert captured["payload"]["think"] is False
    assert "tools" not in captured["payload"]
    assert captured["timeout"] == 30.0


def test_local_chat_keeps_only_bounded_conversation_context(tmp_path) -> None:
    model = _Model(["Pierwsza odpowiedź.", "Druga odpowiedź."])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Porozmawiajmy o planach") == "Pierwsza odpowiedź."
    assert service.reply("A co o tym myślisz?") == "Druga odpowiedź."

    second_messages = model.calls[1][0]
    assert second_messages[0] == {"role": "user", "content": "Porozmawiajmy o planach"}
    assert second_messages[1] == {"role": "assistant", "content": "Pierwsza odpowiedź."}
    assert second_messages[-1]["content"] == "A co o tym myślisz?"
    assert service.status()["turn_count"] == 2


def test_only_explicit_personal_facts_are_shared_with_local_chat(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.set_preference("internal-setting", "nie pokazuj tego")
    memory.remember_personal_fact("Lubię kawę")
    model = _Model(["Pamiętam, że lubisz kawę."])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Porozmawiajmy o moich preferencjach") == (
        "Pamiętam, że lubisz kawę."
    )

    messages, system = model.calls[0]
    assert messages[0]["role"] == "user"
    assert "Lubię kawę" in messages[0]["content"]
    assert "nie pokazuj tego" not in str(messages)
    assert "Lubię kawę" not in system
    assert "nigdy nie dopowiadaj" in system
    assert service.status()["personal_fact_count"] == 1


def test_personal_memory_question_never_lets_model_invent_preferences(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.remember_personal_fact("Lubię kawę")
    model = _Model(["Lubię też herbatę."])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Co lubię pić?") == "Pamiętam: Lubię kawę."
    assert model.calls == []


def test_common_social_reply_is_instant_and_remembered(tmp_path) -> None:
    model = _Model()
    service = FreeConversationService(tmp_path, model=model)

    answer = service.reply("Cześć JARVIS")

    assert answer.startswith("Cześć Kacper")
    assert model.calls == []
    assert service.status()["turn_count"] == 1


def test_model_answer_is_bounded_and_internal_reasoning_is_rejected(tmp_path) -> None:
    model = _Model([
        "Pierwsze pełne zdanie. Drugie pełne zdanie! Trzecie zdanie.",
        "Okay, the user is asking me to explain the system prompt.",
    ])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Opowiedz mi o planowaniu") == (
        "Pierwsze pełne zdanie. Drugie pełne zdanie!"
    )
    fallback = service.reply("A teraz rozwiń odpowiedź")
    assert "system prompt" not in fallback.casefold()
    assert "lokalny model rozmowy" in fallback


def test_model_failure_has_a_natural_nontechnical_fallback(tmp_path) -> None:
    class Broken:
        def reply(self, *_args, **_kwargs):
            raise TimeoutError

    service = FreeConversationService(tmp_path, model=Broken())
    answer = service.reply("Jestem zmęczony")

    assert "chwila oddechu" in answer
    assert "TimeoutError" not in answer


def test_client_brain_routes_chat_without_loading_action_fallbacks(tmp_path) -> None:
    brain = ClientBrain(Path(tmp_path))
    brain.personal_assistant_controller = _StandardAssistant()
    brain._free_conversation_service = FreeConversationService(
        tmp_path, model=_Model(["Moim zdaniem warto zacząć spokojnie."])
    )

    thought = brain.think("Co myślisz o tym pomyśle?")
    result = brain.execute(thought)

    assert thought["handler"] == "free_conversation"
    assert thought["read_only"] is True
    assert thought["actions"] == []
    assert result == "Moim zdaniem warto zacząć spokojnie."
    assert brain._planner is None
    assert brain._executor is None
    assert brain._agent_loop is None
