from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.client_brain import ClientBrain
from app.assistant.free_conversation import FreeConversationService
from app.assistant.project_memory import ProjectMemoryService


class _Model:
    def __init__(self, answers: list[str] | None = None) -> None:
        self.answers = list(answers or ["To jest naturalna odpowiedź."])
        self.calls: list[tuple[list[dict[str, str]], str]] = []
        self.response_budgets: list[int] = []

    def set_response_budget(self, tokens):
        self.response_budgets.append(int(tokens))

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
    assert model.timeout == 50.0
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
    assert captured["payload"]["options"]["num_predict"] == 220
    assert captured["payload"]["options"]["num_ctx"] == 2048
    assert captured["payload"]["keep_alive"] == "5m"
    assert captured["timeout"] == 50.0


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


def test_context_budget_keeps_personal_memory_after_longer_chat(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.remember_personal_fact("Lubię kawę")
    model = _Model([f"Odpowiedź {index}." for index in range(10)])
    service = FreeConversationService(tmp_path, model=model)

    for index in range(8):
        service.reply(f"Co myślisz o planie numer {index}?")
    service.reply("Jak myślisz, co będzie dalej?")

    messages, _system = model.calls[-1]
    assert len(messages) <= 14
    assert "Lubię kawę" in messages[0]["content"]
    assert "planie numer 2" in str(messages)
    assert "planie numer 1" not in str(messages)
    assert all(len(message["content"]) <= 800 for message in messages)


def test_short_acknowledgement_uses_active_conversation_context(tmp_path) -> None:
    model = _Model([
        "Najpierw ustalmy cel. Co chcesz osiągnąć?",
        "W takim razie rozwińmy ten cel krok po kroku.",
    ])
    service = FreeConversationService(tmp_path, model=model)

    service.reply("Porozmawiajmy o moim nowym projekcie")
    answer = service.reply("Okej")

    assert answer == "W takim razie rozwińmy ten cel krok po kroku."
    assert len(model.calls) == 2
    assert model.calls[1][0][0]["content"] == (
        "Porozmawiajmy o moim nowym projekcie"
    )
    assert model.calls[1][0][-1]["content"] == "Okej"


def test_long_emotional_message_gets_a_personalized_model_reply(tmp_path) -> None:
    model = _Model([
        "Rozumiem, że martwi Cię skala projektu. Zacznijmy od części, która blokuje Cię najbardziej.",
    ])
    service = FreeConversationService(tmp_path, model=model)

    answer = service.reply(
        "Jestem zestresowany, bo nie wiem, czy dam radę dokończyć cały duży projekt"
    )

    assert "skala projektu" in answer
    assert len(model.calls) == 1


def test_long_emotional_message_uses_safe_reflex_when_model_fails(tmp_path) -> None:
    class Broken:
        def reply(self, *_args, **_kwargs):
            raise TimeoutError

    service = FreeConversationService(tmp_path, model=Broken())
    answer = service.reply(
        "Jestem zestresowany, bo nie wiem, czy dam radę dokończyć cały duży projekt"
    )

    assert "Zatrzymajmy się" in answer


def test_explicit_followup_without_context_does_not_invent_a_topic(tmp_path) -> None:
    model = _Model(["Nie powinno zostać użyte."])
    service = FreeConversationService(tmp_path, model=model)

    assert service.matches("Kontynuuj rozmowę") is True
    assert "Nie mam teraz aktywnego wątku" in service.reply("Kontynuuj rozmowę")
    assert model.calls == []


def test_explicit_new_topic_discards_old_chat_context(tmp_path) -> None:
    model = _Model([
        "Najpierw omówmy plan projektu.",
        "Podróże najlepiej zacząć planować od terminu i budżetu.",
    ])
    service = FreeConversationService(tmp_path, model=model)
    service.reply("Porozmawiajmy o rozwoju projektu")

    answer = service.reply(
        "Zmieńmy temat. Porozmawiajmy teraz o planowaniu podróży"
    )

    assert "Podróże" in answer
    assert model.calls[1][0] == [{
        "role": "user",
        "content": "Zmieńmy temat. Porozmawiajmy teraz o planowaniu podróży",
    }]
    assert service.status()["turn_count"] == 1
    assert "rozwoju projektu" not in service.recap()


def test_previous_topic_can_be_restored_with_its_original_context(tmp_path) -> None:
    model = _Model([
        "Plan projektu zaczniemy od celu.",
        "Podróż zacznijmy planować od terminu.",
        "Wróćmy więc do ustalania celu projektu.",
    ])
    service = FreeConversationService(tmp_path, model=model)
    service.reply("Porozmawiajmy o rozwoju projektu")
    service.reply("Zmieńmy temat. Porozmawiajmy o podróżach")

    answer = service.reply("Wróćmy do poprzedniego tematu")

    messages = model.calls[2][0]
    assert "ustalania celu projektu" in answer
    assert "rozwoju projektu" in str(messages)
    assert "Podróż zacznijmy" not in str(messages)
    assert "przywrócony poprzedni temat" in messages[-1]["content"]
    assert service.status()["previous_topic_available"] is True


def test_return_to_missing_previous_topic_is_honest_and_instant(tmp_path) -> None:
    model = _Model(["Nie powinno zostać użyte."])
    service = FreeConversationService(tmp_path, model=model)

    answer = service.reply("Przywróć poprzedni temat")

    assert "Nie mam zapisanego poprzedniego tematu" in answer
    assert model.calls == []


def test_legacy_conversation_store_gains_previous_topic_without_data_loss(
    tmp_path,
) -> None:
    path = tmp_path / "data" / "assistant" / "free_conversation.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "version": "1.1",
        "turns": [{
            "user": "Porozmawiajmy o starym projekcie",
            "assistant": "Zacznijmy od jego celu.",
            "created_at": "",
        }],
        "updated_at": "",
        "sequence": 7,
    }), encoding="utf-8")
    service = FreeConversationService(tmp_path, model=_Model())

    service.reply("Zmieńmy temat")

    assert service.status()["previous_topic_available"] is True
    assert service.status()["conversation_sequence"] == 8
    assert "starym projekcie" not in service.recap()


@pytest.mark.parametrize(
    "command",
    (
        "Zmieńmy temat",
        "Nowy temat",
        "Zacznijmy nowy temat",
        "Porozmawiajmy o czymś innym",
        "Zacznijmy od nowa",
    ),
)
def test_new_topic_command_is_instant_and_needs_no_previous_chat(
    tmp_path, command: str,
) -> None:
    model = _Model(["Nie powinno zostać użyte."])
    service = FreeConversationService(tmp_path, model=model)

    assert service.matches(command) is True
    assert service.reply(command) == (
        "Jasne, zaczynamy nowy temat. O czym chcesz teraz porozmawiać?"
    )
    assert model.calls == []


@pytest.mark.parametrize(
    ("command", "instruction_fragment"),
    (
        ("Powiedz to prościej", "prostym językiem"),
        ("Wyjaśnij inaczej", "innymi słowami"),
        ("Nie o to mi chodziło", "Zadaj jedno konkretne pytanie"),
        ("To było za długie", "dwóch najważniejszych zdań"),
        ("To było za krótkie", "jeden konkretny szczegół"),
        ("Podaj przykład", "jeden konkretny, prosty przykład"),
        ("Spróbuj jeszcze raz", "jeszcze raz, ale inaczej"),
        ("Zadaj mi pytanie", "jedno trafne pytanie"),
    ),
)
def test_feedback_rewrites_the_previous_answer_in_context(
    tmp_path, command: str, instruction_fragment: str,
) -> None:
    model = _Model([
        "Pierwsza odpowiedź o planowaniu.",
        "Poprawiona odpowiedź dotycząca tego samego tematu.",
    ])
    service = FreeConversationService(tmp_path, model=model)
    service.reply("Porozmawiajmy o planowaniu projektu")

    answer = service.reply(command)

    assert answer == "Poprawiona odpowiedź dotycząca tego samego tematu."
    second_messages = model.calls[1][0]
    assert second_messages[-2]["content"] == "Pierwsza odpowiedź o planowaniu."
    assert instruction_fragment in second_messages[-1]["content"]
    assert "wykonaj ją teraz" in second_messages[-1]["content"]


def test_feedback_without_previous_answer_is_honest(tmp_path) -> None:
    model = _Model(["Nie powinno zostać użyte."])
    service = FreeConversationService(tmp_path, model=model)

    assert "Nie mam teraz aktywnego wątku" in service.reply(
        "Powiedz to prościej"
    )
    assert model.calls == []


def test_conversation_recap_survives_service_restart_and_skips_small_talk(
    tmp_path,
) -> None:
    model = _Model(["Pierwsza.", "Druga.", "Trzecia."])
    service = FreeConversationService(tmp_path, model=model)
    service.reply("Porozmawiajmy o motywacji")
    service.reply("Okej")
    service.reply("Co zrobić z dużym zadaniem?")

    reloaded = FreeConversationService(tmp_path, model=_Model())
    recap = reloaded.recap()

    assert "Porozmawiajmy o motywacji" in recap
    assert "Co zrobić z dużym zadaniem?" in recap
    assert "Okej" not in recap


def test_empty_conversation_has_an_honest_recap(tmp_path) -> None:
    service = FreeConversationService(tmp_path, model=_Model())

    assert "Nie mam jeszcze zapisanej rozmowy" in service.recap()


def test_clear_history_preserves_explicit_personal_memory(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.remember_personal_fact("Lubię kawę")
    service = FreeConversationService(tmp_path, model=_Model())
    service.reply("Porozmawiajmy o planach")

    assert service.status()["conversation_sequence"] == 1
    assert service.clear_history() == 1
    assert service.status()["turn_count"] == 0
    assert service.status()["conversation_sequence"] == 1
    assert service.status()["previous_topic_available"] is False
    assert service.status()["personal_fact_count"] == 1


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


def test_asking_what_jarvis_knows_uses_explicit_memory(tmp_path) -> None:
    ProjectMemoryService(tmp_path).remember_personal_fact("Lubię kawę")
    model = _Model(["Nie powinno zostać użyte."])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Co o mnie wiesz?") == "Pamiętam: Lubię kawę."
    assert model.calls == []


def test_model_answer_is_bounded_and_internal_reasoning_is_rejected(tmp_path) -> None:
    sentences = [f"Zdanie {index}." for index in range(1, 10)]
    model = _Model([
        " ".join(sentences),
        "Okay, the user is asking me to explain the system prompt.",
    ])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Opowiedz mi o planowaniu") == " ".join(sentences[:8])
    assert model.response_budgets[0] == 220
    fallback = service.reply("A teraz rozwiń odpowiedź")
    assert "system prompt" not in fallback.casefold()
    assert "lokalny model rozmowy" in fallback


def test_persistent_conversation_styles_control_model_answer_length(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.set_preference(
        "conversation_style", "concise", category="assistant_setting",
    )
    concise_model = _Model(["Pierwsze zdanie. Drugie zdanie. Trzecie zdanie."])
    concise = FreeConversationService(tmp_path, model=concise_model)

    assert concise.reply("Co myślisz o planowaniu?") == "Pierwsze zdanie."
    assert "jednym krótkim" in concise_model.calls[0][1]
    assert concise_model.response_budgets == [80]
    assert concise.status()["conversation_style"] == "concise"

    memory.set_preference(
        "conversation_style", "detailed", category="assistant_setting",
    )
    detailed_model = _Model(["Pierwsze. Drugie. Trzecie."])
    detailed = FreeConversationService(tmp_path, model=detailed_model)

    assert detailed.reply("Jak oceniasz ten pomysł?") == "Pierwsze. Drugie. Trzecie."
    assert "maksymalnie w 12" in detailed_model.calls[0][1]
    assert detailed_model.response_budgets == [360]
    assert detailed.status()["conversation_style"] == "detailed"


def test_default_natural_style_keeps_a_longer_complete_reply(tmp_path) -> None:
    answer = " ".join(f"Naturalne zdanie {index}." for index in range(1, 7))
    model = _Model([answer])
    service = FreeConversationService(tmp_path, model=model)

    assert service.reply("Opowiedz szerzej o tym pomyśle") == answer
    assert "2–8 zdaniach" in model.calls[0][1]
    assert model.response_budgets == [220]
    assert service.status()["conversation_style"] == "natural"


def test_question_mode_controls_model_prompt_and_instant_replies(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.set_preference(
        "conversation_question_mode", "none", category="assistant_setting",
    )
    no_questions_model = _Model(["To jest pełna odpowiedź. Co myślisz?"])
    no_questions = FreeConversationService(tmp_path, model=no_questions_model)

    assert no_questions.reply("Opowiedz mi o tym") == "To jest pełna odpowiedź."
    assert "Nie kończ odpowiedzi pytaniem" in no_questions_model.calls[0][1]
    assert no_questions.status()["conversation_question_mode"] == "none"

    memory.set_preference(
        "conversation_question_mode", "engaged", category="assistant_setting",
    )
    engaged = FreeConversationService(tmp_path, model=_Model())
    instant = engaged.reply("Kim jesteś?")

    assert instant.endswith("?")
    assert "Chcesz powiedzieć o tym trochę więcej?" in instant


def test_question_mode_can_be_changed_directly_without_calling_model(
    tmp_path,
) -> None:
    model = _Model(["Nie powinno zostać użyte."])
    service = FreeConversationService(tmp_path, model=model)

    answer = service.reply("Pytaj mnie częściej")

    assert "częściej" in answer
    assert service.status()["conversation_question_mode"] == "engaged"
    assert model.calls == []


def test_engaged_questions_still_work_with_concise_style(tmp_path) -> None:
    memory = ProjectMemoryService(tmp_path)
    memory.set_preference(
        "conversation_style", "concise", category="assistant_setting",
    )
    memory.set_preference(
        "conversation_question_mode", "engaged", category="assistant_setting",
    )
    service = FreeConversationService(
        tmp_path, model=_Model(["Krótka odpowiedź. Dalszy szczegół."]),
    )

    answer = service.reply("Co myślisz o tym pomyśle?")

    assert answer == (
        "Krótka odpowiedź. Chcesz powiedzieć o tym trochę więcej?"
    )


def test_long_answer_preserves_readable_paragraphs_and_list(tmp_path) -> None:
    answer = (
        "Najpierw ustalmy cel.\n\n"
        "Potem podzielmy pracę na krótkie etapy.\n\n"
        "- Pierwszy etap ma być prosty.\n"
        "- Drugi etap powinien dać widoczny efekt."
    )
    model = _Model([answer])
    service = FreeConversationService(tmp_path, model=model)

    result = service.reply("Pomóż mi dobrze zaplanować ten projekt")

    assert result == answer
    assert "\n\n" in result
    assert "\n- Pierwszy etap" in result
    assert "krótkie, czytelne akapity" in model.calls[0][1]


def test_answer_collapses_excess_blank_lines_without_flattening_text(tmp_path) -> None:
    model = _Model(["Pierwszy akapit.\n\n\n\nDrugi akapit."])
    service = FreeConversationService(tmp_path, model=model)

    result = service.reply("Opowiedz mi o dobrym planie")

    assert result == "Pierwszy akapit.\n\nDrugi akapit."


def test_followup_answer_does_not_start_with_dangling_ellipsis(tmp_path) -> None:
    model = _Model(["...rozbijmy ten temat na mniejsze części. Od czego zaczynamy?"])
    service = FreeConversationService(tmp_path, model=model)

    answer = service.reply("Opowiedz więcej o tym pomyśle")

    assert answer.startswith("Rozbijmy")
    assert not answer.startswith(("...", "…"))


def test_concise_style_also_shortens_instant_replies(tmp_path) -> None:
    ProjectMemoryService(tmp_path).set_preference(
        "conversation_style", "concise", category="assistant_setting",
    )
    service = FreeConversationService(tmp_path, model=_Model())

    answer = service.reply("Jestem zestresowany")

    assert answer.count(".") == 1
    assert "Zatrzymajmy się" in answer


def test_model_failure_has_a_natural_nontechnical_fallback(tmp_path) -> None:
    class Broken:
        def reply(self, *_args, **_kwargs):
            raise TimeoutError

    service = FreeConversationService(tmp_path, model=Broken())
    answer = service.reply("Jestem zmęczony")

    assert "prosił o przerwę" in answer
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
