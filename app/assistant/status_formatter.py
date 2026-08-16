from __future__ import annotations

from typing import Any


class AssistantStatusFormatter:
    """Natural Polish status summaries without internal stage vocabulary."""

    @staticmethod
    def _intent_label(value: object) -> str:
        key = str(value or "").strip().casefold()
        labels = {
            "assistant_status": "sprawdzenie gotowości asystenta",
            "capability_help": "wyświetlenie możliwości JARVIS OS",
            "conversation_status": "sprawdzenie pamięci rozmowy",
            "desktop_status": "sprawdzenie sterowania pulpitem",
            "memory_status": "sprawdzenie pamięci projektów",
            "voice_status": "sprawdzenie głosu",
            "daily_status": "sprawdzenie planu i codziennej pracy",
            "integration_status": "sprawdzenie integracji",
            "gmail_search": "wyszukiwanie wiadomości Gmail",
            "natural_action": "wykonanie ostatniego polecenia",
        }
        return labels.get(
            key, key.replace("_", " ") or "brak wcześniejszego polecenia"
        )

    @staticmethod
    def _count(count: object, one: str, few: str, many: str) -> str:
        value = max(0, int(count or 0))
        ending = value % 10
        word = (
            few
            if ending in (2, 3, 4) and value % 100 not in (12, 13, 14)
            else many
        )
        return f"{value} {one if value == 1 else word}"

    @classmethod
    def full(cls, status: dict[str, Any]) -> str:
        conversation = status["conversation"]
        desktop = status["desktop"]
        memory = status["memory"]
        daily = status["daily_work"]
        active = dict(daily.get("active_workflow", {}) or {})
        reminders = dict(status["productivity"].get("reminders", {}) or {})
        title = str(active.get("title") or "").strip()
        completed = int(active.get("completed_steps", 0) or 0)
        total = int(active.get("total_steps", 0) or 0)
        work = (
            f"ostatnie zadanie „{title}” — {completed} z {total} kroków"
            if title else "brak aktywnego zadania wieloetapowego"
        )
        return (
            "JARVIS jest gotowy do pracy.\nRozmowa: pamiętam "
            f"{cls._count(conversation['turn_count'], 'ostatnią wymianę', 'ostatnie wymiany', 'ostatnich wymian')}.\n"
            "Sterowanie pulpitem: "
            f"{cls._count(desktop['executions'], 'wykonana operacja', 'wykonane operacje', 'wykonanych operacji')}, "
            f"{cls._count(desktop['failure_count'], 'błąd', 'błędy', 'błędów')}.\n"
            "Pamięć: "
            f"{cls._count(memory['project_count'], 'zapisany projekt', 'zapisane projekty', 'zapisanych projektów')} i "
            f"{cls._count(memory['interrupted_count'], 'zadanie', 'zadania', 'zadań')} do wznowienia.\n"
            "Głos: mówię po polsku i możesz przerwać mi w trakcie wypowiedzi.\n"
            f"Codzienna praca: {work}.\nPrzypomnienia: "
            f"{cls._count(reminders.get('pending_count'), 'oczekujące', 'oczekujące', 'oczekujących')}, w tym "
            f"{cls._count(reminders.get('due_count'), 'pilne', 'pilne', 'pilnych')}.\n"
            "Ważne działania wykonuję dopiero po Twoim potwierdzeniu."
        )

    @classmethod
    def conversation(cls, status: dict[str, Any]) -> str:
        result = (
            f"Pamiętam {status['turn_count']} z maksymalnie "
            f"{status['context_limit']} ostatnich wymian rozmowy. "
            f"Ostatnio wykonywałem: {cls._intent_label(status['last_intent'])}."
        )
        target = str(status.get("last_target") or "").strip()
        return result + (f" Ostatni omawiany temat: {target}." if target else "")

    @classmethod
    def desktop(cls, status: dict[str, Any]) -> str:
        result = (
            "Sterowanie pulpitem działa. Wykonałem "
            f"{cls._count(status['executions'], 'operację', 'operacje', 'operacji')}: "
            f"{cls._count(status['success_count'], 'operację', 'operacje', 'operacji')} "
            "z potwierdzonym wynikiem"
        )
        unverified = int(status.get("unverified_count", 0) or 0)
        if unverified:
            result += f", {unverified} bez możliwości sprawdzenia wyniku na ekranie"
        result += f". Liczba błędów: {status['failure_count']}."
        if int(status.get("max_attempts", 1) or 1) > 1:
            result += f" Gdy operacja się nie powiedzie, próbuję maksymalnie {status['max_attempts']} razy."
        return result

    @classmethod
    def memory(cls, status: dict[str, Any]) -> str:
        active = dict(status.get("active_project", {}) or {})
        project = str(active.get("name") or "").strip()
        result = "Mam " + cls._count(
            status["project_count"], "zapisany projekt",
            "zapisane projekty", "zapisanych projektów",
        ) + "."
        result += (
            f" Teraz pracujemy nad projektem „{project}”."
            if project else " Żaden projekt nie jest teraz aktywny."
        )
        return result + " Pamiętam " + cls._count(
            status["preference_count"], "preferencję", "preferencje", "preferencji"
        ) + " i " + cls._count(
            status["interrupted_count"], "przerwane zadanie",
            "przerwane zadania", "przerwanych zadań",
        ) + "."

    @staticmethod
    def voice(status: dict[str, Any]) -> str:
        wake_words = ", ".join(status.get("wake_words", []) or [])
        result = "Głos działa po polsku."
        if status.get("neural_enabled"):
            result += " U\u017cywam lokalnego g\u0142osu dopasowanego do pr\u00f3bki."
        if wake_words:
            result += f" Reaguję na hasła: {wake_words}."
        result += (
            " Możesz przerwać mi w trakcie mówienia."
            if status.get("interrupt_enabled")
            else " Przerywanie wypowiedzi jest obecnie wyłączone."
        )
        return result + (
            " Nasłuch ciągły jest włączony."
            if status.get("continuous_mode")
            else " Nasłuch ciągły jest wyłączony."
        )

    @classmethod
    def daily(
        cls, status: dict[str, Any], reminders: dict[str, Any]
    ) -> str:
        active = dict(status.get("active_workflow", {}) or {})
        title = str(active.get("title") or "").strip()
        phase = str(active.get("status") or "IDLE").upper()
        completed = int(active.get("completed_steps", 0) or 0)
        total = int(active.get("total_steps", 0) or 0)
        next_step = str(active.get("next_step") or "").strip()
        if not title:
            work = "Nie masz teraz aktywnego zadania wieloetapowego."
        elif phase == "COMPLETED":
            work = f"Ostatnie zadanie „{title}” jest zakończone. Wykonano "
            work += cls._count(total, "cały krok", "wszystkie kroki", "wszystkich kroków") + "."
        elif phase == "PAUSED":
            work = f"Zadanie „{title}” jest wstrzymane po {completed} z {total} kroków."
        else:
            work = f"Zadanie „{title}” ma wykonane {completed} z {total} kroków."
            if next_step:
                work += f" Następny krok: {next_step}."
        pending = int(reminders.get("pending_count", 0) or 0)
        due = int(reminders.get("due_count", 0) or 0)
        if not pending:
            return work + " Nie masz oczekujących przypomnień."
        reminder = dict(reminders.get("next_reminder", {}) or {})
        text = str(reminder.get("text") or "").strip()
        result = work + f" Masz {pending} oczekujących przypomnień"
        result += f", w tym {due} pilnych" if due else ""
        result += "."
        return result + (f" Najbliższe: „{text}”." if text else "")
