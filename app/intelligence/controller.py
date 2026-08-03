from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from app.core.project_paths import resolve_project_root
from app.intelligence.autonomy_center import AutonomyControlCenterV2
from app.intelligence.brain_context import BrainContextV2, fold
from app.intelligence.desktop_orchestrator import DesktopAgentV2
from app.intelligence.memory_index import MemoryIndexV2
from app.intelligence.vision_runtime import VisionRuntimeV3


class IntelligenceSuiteController:
    """B101-B105 cohesive local intelligence and autonomy runtime."""

    STAGES = {
        "B101": "VISION_3_READY",
        "B102": "BRAIN_2_READY",
        "B103": "DESKTOP_AGENT_2_READY",
        "B104": "MEMORY_2_READY",
        "B105": "AUTONOMY_CONTROL_CENTER_2_READY",
    }

    READ_ONLY = {
        "suite_status", "vision_status", "brain_status", "desktop_status",
        "memory_status", "memory_search", "autonomy_status", "brain_plan",
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.vision = VisionRuntimeV3(self.project_root)
        self.brain = BrainContextV2(self.project_root)
        self.desktop = DesktopAgentV2(self.project_root, vision=self.vision)
        self.memory = MemoryIndexV2(self.project_root)
        self.autonomy = AutonomyControlCenterV2(self.project_root)

    @staticmethod
    def matches(command: object) -> bool:
        value = fold(command)
        phrases = (
            "status b101", "status vision 3", "status wizji 3", "vision 3.0",
            "zapisz obserwacje vision", "zapisz obserwację vision",
            "status b102", "status brain 2", "status mozgu 2", "status mózgu 2",
            "przeanalizuj polecenie 2.0", "plan brain 2",
            "status b103", "status desktop agent 2", "status pulpitu 2",
            "status b104", "status pamieci 2", "status pamięci 2",
            "zapamietaj w pamieci 2", "zapamiętaj w pamięci 2",
            "znajdz w pamieci 2", "znajdź w pamięci 2",
            "status b105", "status autonomii 2", "centrum autonomii 2",
            "utworz zadanie autonomii 2", "utwórz zadanie autonomii 2",
            "uruchom zadanie autonomii 2", "nastepny etap autonomii 2",
            "następny etap autonomii 2", "wstrzymaj autonomie 2",
            "wstrzymaj autonomię 2", "wznow autonomie 2", "wznów autonomię 2",
            "anuluj autonomie 2", "anuluj autonomię 2", "status b101-b105",
            "centrum inteligencji", "intelligence center",
        )
        return any(phrase in value for phrase in phrases)

    def plan(self, command: object) -> dict[str, Any]:
        intent = self.intent(command)
        return {
            "command": str(command),
            "goal": "Obsłużyć funkcje inteligencji B101–B105",
            "plan": [
                "Rozpoznać usługę Vision, Brain, Desktop, Memory albo Autonomy",
                "Odczytać trwały kontekst i bieżący stan",
                "Sprawdzić ryzyko oraz wymóg potwierdzenia",
                "Wykonać ograniczoną operację lokalną",
                "Zapisać wynik, postęp i audyt stanu",
            ],
            "actions": [],
            "can_execute": True,
            "handler": "personal_assistant",
            "assistant_intent": intent,
            "read_only": intent in self.READ_ONLY,
        }

    def handle(self, command: object) -> str:
        text = " ".join(str(command).split()).strip()
        intent = self.intent(text)
        if intent == "suite_status":
            return self._full_status()
        if intent == "vision_status":
            return self._vision_status()
        if intent == "vision_demo":
            observation = self.vision.observe(
                "JARVIS OS",
                [
                    {"label": "Konsola operacyjna", "role": "button", "confidence": 0.98},
                    {"label": "Wykonaj", "role": "button", "confidence": 0.99},
                ],
                source="B101 demo",
            )
            return f"B101: zapisano obserwację {observation['observation_id']} z 2 elementami."
        if intent == "brain_status":
            return self._brain_status()
        if intent == "brain_plan":
            target = self._after_colon(text) or "Pokaż status systemu"
            plan = self.brain.plan(target)
            return (
                f"B102: intencja {plan['intent']}, ryzyko {plan['risk']}, "
                f"kroki {len(plan['steps'])}."
            )
        if intent == "desktop_status":
            return self._desktop_status()
        if intent == "memory_status":
            return self._memory_status()
        if intent == "memory_add":
            content = self._after_colon(text)
            if not content:
                raise ValueError("Użyj: Zapamiętaj w pamięci 2.0: treść.")
            entry = self.memory.remember(content, category="user")
            return f"B104: zapisano pamięć {entry['memory_id']}."
        if intent == "memory_search":
            query = self._after_colon(text) or re.sub(
                r"^.*?(?:pamięci|pamieci)\s*2(?:\.0)?", "", text, flags=re.IGNORECASE
            ).strip(" :")
            results = self.memory.search(query)
            if not results:
                return "B104: brak pasujących wspomnień."
            return "B104: " + " | ".join(item["text"] for item in results[:3])
        if intent == "autonomy_status":
            return self._autonomy_status()
        if intent == "autonomy_create":
            title, steps = self._parse_job(text)
            job = self.autonomy.create_job(title, steps)
            return f"B105: utworzono {job['job_id']} z {len(job['steps'])} krokami."
        if intent == "autonomy_start":
            job = self.autonomy.start()
            return f"B105: uruchomiono zadanie „{job['title']}”."
        if intent == "autonomy_advance":
            job = self.autonomy.advance("Zatwierdzono ręcznie")
            return self._job_progress(job)
        if intent == "autonomy_pause":
            return self._job_progress(self.autonomy.pause())
        if intent == "autonomy_resume":
            return self._job_progress(self.autonomy.resume())
        if intent == "autonomy_cancel":
            return self._job_progress(self.autonomy.cancel())
        return self._full_status()

    def status(self) -> dict[str, Any]:
        return {
            "status": "INTELLIGENCE_DESKTOP_MEMORY_SUITE_READY",
            "stages": dict(self.STAGES),
            "vision": self.vision.status(),
            "brain": self.brain.status(),
            "desktop": self.desktop.status(),
            "memory": self.memory.status(),
            "autonomy": self.autonomy.status(),
            "safety": {"auto_approve": False, "max_active_executions": 1, "remote_code": False},
        }

    @staticmethod
    def intent(command: object) -> str:
        value = fold(command)
        if "status b101-b105" in value or "centrum inteligencji" in value or "intelligence center" in value:
            return "suite_status"
        if "zapisz obserw" in value and "vision" in value:
            return "vision_demo"
        if "status b101" in value or "vision 3" in value or "wizji 3" in value:
            return "vision_status"
        if "przeanalizuj polecenie 2" in value or "plan brain 2" in value:
            return "brain_plan"
        if "status b102" in value or "brain 2" in value or "mozgu 2" in value:
            return "brain_status"
        if "status b103" in value or "desktop agent 2" in value or "pulpitu 2" in value:
            return "desktop_status"
        if "zapamietaj w pamieci 2" in value:
            return "memory_add"
        if "znajdz w pamieci 2" in value:
            return "memory_search"
        if "status b104" in value or "status pamieci 2" in value:
            return "memory_status"
        if "utworz zadanie autonomii 2" in value:
            return "autonomy_create"
        if "uruchom zadanie autonomii 2" in value:
            return "autonomy_start"
        if "nastepny etap autonomii 2" in value:
            return "autonomy_advance"
        if "wstrzymaj autonomie 2" in value:
            return "autonomy_pause"
        if "wznow autonomie 2" in value:
            return "autonomy_resume"
        if "anuluj autonomie 2" in value:
            return "autonomy_cancel"
        if "status b105" in value or "status autonomii 2" in value or "centrum autonomii 2" in value:
            return "autonomy_status"
        return "suite_status"

    def _full_status(self) -> str:
        status = self.status()
        autonomy = status["autonomy"]["active_job"]
        return (
            "B101–B105: Vision 3, Brain 2, Desktop Agent 2, Memory 2 i Centrum Autonomii 2 GOTOWE. "
            f"Pamięć: {status['memory']['entry_count']}; zadania: {status['autonomy']['job_count']}; "
            f"aktywne: {autonomy.get('title') or 'brak'}."
        )

    def _vision_status(self) -> str:
        value = self.vision.status()
        return f"B101: {value['status']}; obserwacje {value['observation_count']}; elementy {value['element_count']}."

    def _brain_status(self) -> str:
        value = self.brain.status()
        return f"B102: {value['status']}; plany {value['turn_count']}; ostatnia intencja {value['last_intent'] or 'brak'}."

    def _desktop_status(self) -> str:
        value = self.desktop.status()
        return f"B103: {value['status']}; transakcje {value['transaction_count']}; potwierdzone {value['verified_count']}; błędy {value['failure_count']}."

    def _memory_status(self) -> str:
        value = self.memory.status()
        return f"B104: {value['status']}; wpisy {value['entry_count']}; kategorie {value['category_count']}."

    def _autonomy_status(self) -> str:
        value = self.autonomy.status()
        active = value["active_job"]
        return (
            f"B105: {value['status']}; kolejka {value['queued_count']}; "
            f"aktywne {active.get('title') or 'brak'}; postęp {active.get('progress_percent', 0)}%."
        )

    @staticmethod
    def _after_colon(text: str) -> str:
        return text.split(":", 1)[1].strip() if ":" in text else ""

    @staticmethod
    def _parse_job(text: str) -> tuple[str, list[str]]:
        payload = IntelligenceSuiteController._after_colon(text)
        if not payload:
            raise ValueError("Użyj: Utwórz zadanie autonomii 2.0: Nazwa | krok 1; krok 2.")
        if "|" in payload:
            title, raw_steps = payload.split("|", 1)
        else:
            title, raw_steps = "Zadanie B105", payload
        steps = [item.strip() for item in raw_steps.split(";") if item.strip()]
        return title.strip(), steps

    @staticmethod
    def _job_progress(job: dict[str, Any]) -> str:
        steps = list(job.get("steps", []) or [])
        done = sum(item.get("status") == "COMPLETED" for item in steps)
        return f"B105: {job.get('status')}; {job.get('title')}; postęp {done}/{len(steps)}."
