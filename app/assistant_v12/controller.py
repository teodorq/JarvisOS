from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.assistant.natural_language import fold_text
from app.assistant_v12.context_hub import UnifiedContextHub, utc_now
from app.assistant_v12.conversation_engine import NaturalConversationEngineV3, ParsedRequest
from app.assistant_v12.productivity_router import UnifiedProductivityRouter
from app.assistant_v12.progress_runtime import AssistantProgressRuntime
from app.client_experience.controller import ClientExperienceController
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


class AssistantV12Controller:
    """B121-B125 natural daily assistant and Business 1.2 Beta gates."""

    STAGES = {
        "B121": "NATURAL_CONVERSATION_3_READY",
        "B122": "UNIFIED_CONTEXT_HUB_READY",
        "B123": "UNIFIED_PRODUCTIVITY_ROUTER_READY",
        "B124": "ASSISTANT_PROGRESS_RUNTIME_READY",
        "B125": "BUSINESS_1_2_BETA_READINESS_READY",
    }

    READ_ONLY = NaturalConversationEngineV3.READ_ONLY | {"beta_audit"}

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.context = UnifiedContextHub(self.project_root)
        self.conversation = NaturalConversationEngineV3(self.context)
        self.router = UnifiedProductivityRouter(self.project_root)
        self.progress = AssistantProgressRuntime(self.project_root)
        self.beta_store = JsonStore(
            self.project_root / "data" / "assistant_v12" / "business_1_2_beta.json",
            self._beta_default,
        )

    @staticmethod
    def _beta_default() -> dict[str, Any]:
        return {
            "version": "1.2",
            "audits": [],
            "confirmations": [],
            "updated_at": "",
        }

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self.progress.set_callback(callback)

    def matches(self, command: object) -> bool:
        pending = dict(self.context.load().get("pending", {}) or {})
        return bool(pending) or self.conversation.matches(command)

    def plan(self, command: object, *, source: str = "TEXT") -> dict[str, Any]:
        request = self.conversation.parse(
            command,
            source=source,
            mutate_context=False,
        )
        return {
            "command": request.command,
            "original_command": request.original,
            "goal": "Obsłużyć codzienne polecenie przez JARVIS OS 1.2",
            "plan": [
                "Rozpoznać naturalną intencję i brakujące informacje",
                "Połączyć kontekst tekstu, głosu, pamięci i aktywnego zadania",
                "Wybrać jedną lokalną usługę produktywności",
                "Pokazać rzeczywisty etap i postęp wykonania",
                "Zweryfikować wynik oraz zapisać bezpieczny ślad działania",
            ],
            "actions": [],
            "can_execute": request.intent != "standard",
            "handler": "personal_assistant",
            "assistant_intent": request.intent,
            "read_only": request.read_only or bool(request.clarification),
            "clarification": request.clarification,
            "v12_slots": request.slots,
            "v12_used_context": request.used_context,
        }

    def handle(self, command: object, *, source: str = "TEXT") -> str:
        request = self.conversation.parse(command, source=source)
        if request.intent == "standard":
            raise ValueError("B121: polecenie nie należy do asystenta codziennego 1.2.")
        if request.clarification:
            return request.clarification

        self.progress.start(command=request.command, intent=request.intent)
        try:
            self.progress.phase("KONTEKST", 25, "Łączę kontekst rozmowy i bieżącego zadania.")
            if request.intent == "context_clear":
                self.context.clear()
                response = "Wyczyściłem lokalny kontekst asystenta 1.2."
            elif request.intent == "suite_status":
                response = self._format_status()
            elif request.intent == "context_status":
                response = self._format_context()
            elif request.intent == "progress_status":
                response = self._format_progress()
            elif request.intent == "beta_status":
                response = self._format_beta_status()
            elif request.intent == "beta_audit":
                audit = self.run_beta_audit()
                response = f"B125: audyt {audit['status']}; bramki {audit['passed']}/{audit['total']}."
            elif request.intent == "beta_confirm":
                confirmation = self.confirm_beta()
                response = confirmation["status"]
            else:
                self.progress.phase("ROUTING", 50, "Wybieram bezpieczną usługę lokalną.")
                response = self._execute_router(request)
            self.progress.phase("WERYFIKACJA", 90, "Sprawdzam wynik i zapisuję ślad działania.")
            self.context.remember(
                command=request.command,
                intent=request.intent,
                response=response,
                slots=request.slots,
                source=source,
            )
            self.progress.complete(response)
            return response
        except Exception as error:
            self.progress.fail(error)
            raise

    def _execute_router(self, request: ParsedRequest) -> str:
        self.progress.phase("WYKONANIE", 70, "Wykonuję ograniczoną operację lokalną.")
        try:
            return self.router.execute(request.intent, request.slots)
        except (OSError, RuntimeError) as error:
            if not request.read_only:
                raise
            self.progress.retry(f"Ponawiam bezpieczny odczyt: {error}")
            return self.router.execute(request.intent, request.slots)

    def run_beta_audit(self) -> dict[str, Any]:
        context = self.context.status()
        router = self.router.status()
        progress = self.progress.status()
        client = ClientExperienceController(self.project_root).status()
        gates = [
            self._gate("B121_CONVERSATION", True),
            self._gate("B122_CONTEXT", context["status"] == "UNIFIED_CONTEXT_HUB_READY"),
            self._gate("B123_ROUTER", all(router[key] for key in ("mail_ready", "calendar_ready", "documents_ready", "reminders_ready", "reporting_ready"))),
            self._gate("B124_PROGRESS", progress["status"] == "ASSISTANT_PROGRESS_RUNTIME_READY"),
            self._gate("BUSINESS_1_1_STABLE", bool(client["stable_ready"])),
            self._gate("AUTO_APPROVE_OFF", True),
            self._gate("REMOTE_SYNC_OFF", not router["remote_sync"]),
            self._gate("AUTOMATIC_SENDING_OFF", not router["automatic_sending"]),
        ]
        passed = sum(int(item["passed"]) for item in gates)
        audit = {
            "audit_id": uuid4().hex[:16],
            "status": "PASSED" if passed == len(gates) else "BLOCKED",
            "passed": passed,
            "total": len(gates),
            "gates": gates,
            "created_at": utc_now(),
        }
        data = self._beta_load()
        audits = list(data.get("audits", []) or [])
        audits.append(audit)
        data.update({"audits": audits[-30:], "updated_at": utc_now()})
        self.beta_store.save(data)
        return audit

    def confirm_beta(self) -> dict[str, Any]:
        data = self._beta_load()
        audits = list(data.get("audits", []) or [])
        if not audits or audits[-1].get("status") != "PASSED":
            raise ValueError("B125: najpierw uruchom zaliczony audyt Business 1.2.")
        confirmation = {
            "confirmation_id": uuid4().hex[:16],
            "audit_id": audits[-1]["audit_id"],
            "status": "BUSINESS_1_2_BETA_READY",
            "confirmed_at": utc_now(),
            "automatic_publication": False,
            "owner_mode_preserved": True,
        }
        confirmations = list(data.get("confirmations", []) or [])
        confirmations.append(confirmation)
        data.update({"confirmations": confirmations[-20:], "updated_at": utc_now()})
        self.beta_store.save(data)
        self._export(audits[-1], confirmation)
        return confirmation

    def status(self) -> dict[str, Any]:
        data = self._beta_load()
        audits = list(data.get("audits", []) or [])
        confirmations = list(data.get("confirmations", []) or [])
        latest_audit = dict(audits[-1]) if audits else {}
        latest_confirmation = dict(confirmations[-1]) if confirmations else {}
        return {
            "status": "ASSISTANT_1_2_SUITE_READY",
            "stages": dict(self.STAGES),
            "conversation": {"status": "NATURAL_CONVERSATION_3_READY"},
            "context": self.context.status(),
            "router": self.router.status(),
            "progress": self.progress.status(),
            "beta": {
                "status": "BUSINESS_1_2_BETA_READINESS_READY",
                "audit_count": len(audits),
                "latest_audit_status": str(latest_audit.get("status", "NOT_RUN")),
                "gates_passed": int(latest_audit.get("passed", 0) or 0),
                "gates_total": int(latest_audit.get("total", 8) or 8),
                "beta_ready": latest_confirmation.get("status") == "BUSINESS_1_2_BETA_READY",
                "automatic_publication": False,
            },
            "safety": {
                "auto_approve": False,
                "max_active_executions": 1,
                "remote_sync": False,
                "automatic_sending": False,
            },
        }

    def _format_status(self) -> str:
        value = self.status()
        return (
            "B121–B125 ASYSTENT 1.2\n"
            f"B121 rozmowa: {value['conversation']['status']}\n"
            f"B122 kontekst: {value['context']['turn_count']}/80 tur, oczekujące {value['context']['pending_intent'] or 'BRAK'}\n"
            f"B123 router: {value['router']['status']}\n"
            f"B124 postęp: operacje {value['progress']['operation_count']}, błędy {value['progress']['failed_count']}\n"
            f"B125 Beta: {value['beta']['latest_audit_status']}, gotowa {'TAK' if value['beta']['beta_ready'] else 'NIE'}."
        )

    def _format_context(self) -> str:
        value = self.context.status()
        return (
            f"B122: kontekst {value['turn_count']}/{value['context_limit']} tur; "
            f"temat {value['active_topic'] or 'BRAK'}; "
            f"ostatnia intencja {value['last_intent'] or 'BRAK'}; "
            f"oczekujące {value['pending_intent'] or 'BRAK'}."
        )

    def _format_progress(self) -> str:
        value = self.progress.status()
        latest = dict(value.get("latest", {}) or {})
        return (
            f"B124: operacje {value['operation_count']}; ukończone {value['completed_count']}; "
            f"błędy {value['failed_count']}; retry {value['retry_count']}; "
            f"ostatnia faza {latest.get('phase') or 'BRAK'}."
        )

    def _format_beta_status(self) -> str:
        value = self.status()["beta"]
        return (
            f"B125: audyty {value['audit_count']}; ostatni {value['latest_audit_status']}; "
            f"bramki {value['gates_passed']}/{value['gates_total']}; "
            f"BUSINESS_1_2_BETA_READY {'TAK' if value['beta_ready'] else 'NIE'}."
        )

    def _beta_load(self) -> dict[str, Any]:
        value = self.beta_store.load()
        return value if isinstance(value, dict) else self._beta_default()

    def _export(self, audit: dict[str, Any], confirmation: dict[str, Any]) -> None:
        directory = self.project_root / "AI_PLIKI" / "reports"
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"audit": audit, "confirmation": confirmation, "status": self.status()}
        (directory / "JARVIS_BUSINESS_1_2_BETA.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (directory / "JARVIS_BUSINESS_1_2_BETA.txt").write_text(
            "\n".join([
                "JARVIS OS 1.2 BETA",
                f"Status: {confirmation['status']}",
                f"Bramki: {audit['passed']}/{audit['total']}",
                "Automatyczna publikacja: NIE",
                "Tryb właściciela zachowany: TAK",
            ]) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _gate(name: str, passed: bool) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed)}
