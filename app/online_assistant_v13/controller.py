from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Callable
from uuid import uuid4

from app.assistant.natural_language import fold_text
from app.assistant_v12.context_hub import utc_now
from app.assistant_v12.progress_runtime import AssistantProgressRuntime
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import clip
from app.online_assistant_v13.calendar_intelligence import CalendarIntelligenceService
from app.online_assistant_v13.drive_documents import DriveDocumentService
from app.online_assistant_v13.gmail_workflows import GmailWorkflowService
from app.online_assistant_v13.reliability import WorkspaceReliabilityService


class OnlineAssistantV13Controller:
    """B131-B135 safer Google Workspace workflows and Online Assistant 1.3 Beta."""

    STAGES = {
        "B131": "WORKSPACE_RELIABILITY_READY",
        "B132": "GMAIL_WORKFLOWS_READY",
        "B133": "CALENDAR_INTELLIGENCE_READY",
        "B134": "DRIVE_DOCUMENTS_READY",
        "B135": "ONLINE_ASSISTANT_1_3_BETA_READINESS_READY",
    }
    READ_ONLY_INTENTS = {
        "v13_status", "reliability_probe", "gmail_briefing",
        "calendar_week", "calendar_slots", "drive_v13_search",
        "drive_v13_summary", "drive_versions", "beta_audit",
    }
    WRITE_INTENTS = {
        "gmail_v13_draft", "gmail_v13_send", "gmail_archive", "gmail_label",
        "calendar_v13_create", "drive_create_version", "beta_confirm",
    }

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        provider: Any,
        previous: Any,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider
        self.previous = previous
        kwargs = {"sleep": sleep} if sleep is not None else {}
        self.reliability = WorkspaceReliabilityService(
            self.project_root, provider=provider, **kwargs
        )
        self.gmail = GmailWorkflowService(
            self.project_root, provider=provider, reliability=self.reliability
        )
        self.calendar = CalendarIntelligenceService(
            self.project_root, provider=provider, reliability=self.reliability
        )
        self.drive = DriveDocumentService(
            self.project_root, provider=provider, reliability=self.reliability
        )
        self.progress = AssistantProgressRuntime(self.project_root)
        self.beta_store = JsonStore(
            self.project_root / "data" / "online_assistant_v13" / "online_assistant_1_3_beta.json",
            lambda: {
                "version": "1.3-beta", "audits": [], "confirmations": [],
                "updated_at": "",
            },
        )

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self.progress.set_callback(callback)

    @staticmethod
    def matches(command: object) -> bool:
        text = fold_text(command)
        phrases = (
            "asystent online 1.3", "online assistant 1.3", "business 1.3 beta",
            "niezawodnosc google workspace", "stan sesji google", "status b131",
            "skrzynka pracy gmail", "skrzynke pracy gmail", "workflow gmail", "archiwizuj gmail",
            "etykiete gmail", "etykieta gmail", "status b132",
            "plan tygodnia google", "zaproponuj termin google",
            "zaproponuj terminy google", "status b133",
            "dokument online 1.3", "wersje dokumentow online",
            "wyszukaj dokument online", "podsumuj dokument online", "status b134",
            "audyt b135", "test b135", "potwierdz b135", "status b135",
            "b131", "b132", "b133", "b134", "b135",
        )
        return any(phrase in text for phrase in phrases)

    def intent(self, command: object) -> str:
        text = fold_text(command)
        rules = (
            ("beta_confirm", ("potwierdz b135", "potwierdz business 1.3 beta", "potwierdz asystenta online 1.3")),
            ("beta_audit", ("uruchom audyt b135", "uruchom test b135", "audyt b135", "test business 1.3 beta")),
            ("gmail_v13_send", ("wyslij szkic gmail 1.3", "wyslij szkic workflow gmail")),
            ("gmail_v13_draft", ("utworz szkic gmail 1.3", "przygotuj szkic workflow gmail")),
            ("gmail_archive", ("archiwizuj gmail", "zarchiwizuj gmail")),
            ("gmail_label", ("dodaj etykiete gmail", "etykieta gmail", "oznacz gmail etykieta")),
            ("gmail_briefing", ("skrzynka pracy gmail", "skrzynke pracy gmail", "podsumuj workflow gmail", "pokaz workflow gmail")),
            ("calendar_v13_create", ("utworz wydarzenie google 1.3", "dodaj spotkanie google 1.3")),
            ("calendar_slots", ("zaproponuj termin google", "zaproponuj terminy google", "wolne terminy google")),
            ("calendar_week", ("plan tygodnia google", "analiza kalendarza 1.3")),
            ("drive_create_version", ("utworz dokument online 1.3", "zapisz dokument online 1.3")),
            ("drive_versions", ("wersje dokumentow online", "pokaz wersje dokumentow")),
            ("drive_v13_summary", ("podsumuj dokument online", "podsumuj dokument 1.3")),
            ("drive_v13_search", ("wyszukaj dokument online", "szukaj dokumentow 1.3")),
            ("reliability_probe", ("sprawdz niezawodnosc google workspace", "stan sesji google", "test polaczenia b131")),
            ("v13_status", ("status asystenta online 1.3", "status business 1.3 beta", "status b135", "status b131")),
        )
        for intent, phrases in rules:
            if any(phrase in text for phrase in phrases):
                return intent
        return "v13_status"

    def plan(self, command: object) -> dict[str, Any]:
        intent = self.intent(command)
        return {
            "command": str(command).strip(),
            "goal": "Obsłużyć Google Workspace przez Online Assistant 1.3 Beta",
            "plan": [
                "Sprawdzić sesję OAuth i stan usług Google Workspace",
                "Użyć maksymalnie trzech prób wyłącznie dla bezpiecznego odczytu",
                "Wymagać potwierdzenia przed każdą zmianą, zapisem lub wysyłką",
                "Zapisać ograniczony checkpoint bez tokenów i sekretów",
                "Zweryfikować wynik przez bramki B131–B135",
            ],
            "actions": [], "can_execute": True, "handler": "personal_assistant",
            "assistant_intent": intent,
            "read_only": intent in self.READ_ONLY_INTENTS,
            "online_operation": True,
            "requires_confirmation": intent in self.WRITE_INTENTS,
        }

    def handle(self, command: object) -> str:
        text = str(command).strip()
        intent = self.intent(text)
        self.progress.start(command=text, intent=intent)
        try:
            self.progress.phase("SESJA", 15, "Sprawdzam sesję, retry i bezpieczny tryb offline.")
            response = self._dispatch(intent, text)
            self.progress.phase("WERYFIKACJA", 92, "Zapisuję wynik bez tokenów i sekretów.")
            self.progress.complete(response)
            return response
        except Exception as error:
            self.progress.fail(error)
            if isinstance(error, (ValueError, RuntimeError)):
                raise ValueError(str(error)) from None
            raise

    def _dispatch(self, intent: str, text: str) -> str:
        if intent == "v13_status":
            return self._format_status()
        if intent == "reliability_probe":
            probe = self.reliability.probe()
            return (
                f"B131: Google Workspace {probe['status']}; tryb {probe['mode']}; "
                f"Gmail {'OK' if probe['gmail'] else 'NIE'}, "
                f"Kalendarz {'OK' if probe['calendar'] else 'NIE'}, "
                f"Dysk {'OK' if probe['drive'] else 'NIE'}."
            )
        if intent == "gmail_briefing":
            return self._format_gmail(self.gmail.briefing())
        if intent == "gmail_v13_draft":
            recipient, subject, body = self._draft_slots(text)
            result = self.gmail.create_draft(recipient, subject, body)
            return f"B132: szkic {result['draft_id']} utworzony; automatyczna wysyłka NIE."
        if intent == "gmail_v13_send":
            result = self.gmail.send_draft(self._tail(text, ("wyslij szkic gmail 1.3", "wyslij szkic workflow gmail")))
            return f"B132: szkic wysłany po potwierdzeniu; message_id {result['message_id']}."
        if intent == "gmail_archive":
            result = self.gmail.archive(self._tail(text, ("archiwizuj gmail", "zarchiwizuj gmail")))
            return f"B132: wiadomość {result['message_id']} zarchiwizowana po potwierdzeniu."
        if intent == "gmail_label":
            message_id, label = self._label_slots(text)
            result = self.gmail.add_label(message_id, label)
            return f"B132: dodano etykietę „{result['label']}” do wiadomości {result['message_id']}."
        if intent == "calendar_week":
            return self._format_week(self.calendar.week())
        if intent == "calendar_slots":
            return self._format_slots(self.calendar.suggest_slots(duration_minutes=self._duration(text)))
        if intent == "calendar_v13_create":
            title, start, duration = self._calendar_slots(text)
            result = self.calendar.create_event(title, start, duration)
            return f"B133: utworzono wydarzenie „{result['title']}” na {result['start_at']}."
        if intent == "drive_v13_search":
            query = self._tail(text, ("wyszukaj dokument online", "szukaj dokumentow 1.3"))
            return self._format_drive(self.drive.search(query), query)
        if intent == "drive_v13_summary":
            file_id, mime, name = self._summary_slots(text)
            result = self.drive.summarize(file_id, mime, name=name)
            return f"B134: podsumowanie „{result['name'] or result['file_id']}”: {result['summary']}"
        if intent == "drive_create_version":
            title, content = self._document_slots(text)
            result = self.drive.create_version(title, content)
            return f"B134: zapisano „{result['name']}” jako wersję {result['version']}."
        if intent == "drive_versions":
            return self._format_versions(self.drive.versions())
        if intent == "beta_audit":
            audit = self.run_beta_audit()
            return f"B135: audyt {audit['status']}; bramki {audit['passed']}/{audit['total']}."
        if intent == "beta_confirm":
            return self.confirm_beta()["status"]
        raise ValueError("B131–B135: nie rozpoznano polecenia Online Assistant 1.3.")

    def run_beta_audit(self) -> dict[str, Any]:
        previous = dict(self.previous.status() or {})
        connection = dict(previous.get("connection", {}) or {})
        rc = dict(previous.get("rc", {}) or {})
        probe = self.reliability.probe()
        gates = [
            self._gate("BUSINESS_1_2_STABLE_RC_READY", bool(rc.get("rc_ready"))),
            self._gate("GOOGLE_DEPENDENCIES_READY", bool(connection.get("dependency_ready"))),
            self._gate("OAUTH_CLIENT_CONFIGURED", bool(connection.get("client_configured"))),
            self._gate("LOCAL_TOKEN_PRESENT", bool(connection.get("token_present"))),
            self._gate("LIVE_GMAIL", bool(probe.get("gmail"))),
            self._gate("LIVE_CALENDAR", bool(probe.get("calendar"))),
            self._gate("LIVE_DRIVE", bool(probe.get("drive"))),
            self._gate("READ_RETRY_BOUNDED", self.reliability.max_read_attempts <= 3),
            self._gate("WRITE_RETRY_DISABLED", not self.reliability.status()["write_retry_enabled"]),
            self._gate("GMAIL_AUTOMATIC_SENDING_OFF", not self.gmail.status()["automatic_sending"]),
            self._gate("WRITES_REQUIRE_CONFIRMATION", True),
            self._gate("SECRETS_OUTSIDE_PROJECT", not str(connection.get("token_path", "")).startswith(str(self.project_root))),
        ]
        passed = sum(int(gate["passed"]) for gate in gates)
        audit = {
            "audit_id": uuid4().hex[:16], "status": "PASSED" if passed == len(gates) else "BLOCKED",
            "passed": passed, "total": len(gates), "gates": gates, "created_at": utc_now(),
        }
        data = self._load_beta()
        audits = list(data.get("audits", []) or [])
        audits.append(audit)
        data.update({"audits": audits[-30:], "updated_at": utc_now()})
        self.beta_store.save(data)
        return audit

    def confirm_beta(self) -> dict[str, Any]:
        data = self._load_beta()
        audits = list(data.get("audits", []) or [])
        if not audits or audits[-1].get("status") != "PASSED":
            raise ValueError("B135: najpierw uruchom zaliczony audyt B135.")
        confirmation = {
            "confirmation_id": uuid4().hex[:16], "audit_id": audits[-1]["audit_id"],
            "status": "ONLINE_ASSISTANT_1_3_BETA_READY", "confirmed_at": utc_now(),
            "automatic_sending": False, "automatic_publication": False,
            "writes_require_confirmation": True,
        }
        confirmations = list(data.get("confirmations", []) or [])
        confirmations.append(confirmation)
        data.update({"confirmations": confirmations[-20:], "updated_at": utc_now()})
        self.beta_store.save(data)
        self._export(audits[-1], confirmation)
        return confirmation

    def status(self) -> dict[str, Any]:
        data = self._load_beta()
        audits = list(data.get("audits", []) or [])
        confirmations = list(data.get("confirmations", []) or [])
        latest_audit = dict(audits[-1]) if audits else {}
        latest_confirmation = dict(confirmations[-1]) if confirmations else {}
        return {
            "status": "ONLINE_ASSISTANT_1_3_BETA_SUITE_READY",
            "stages": dict(self.STAGES),
            "reliability": self.reliability.status(),
            "gmail": self.gmail.status(),
            "calendar": self.calendar.status(),
            "drive": self.drive.status(),
            "progress": self.progress.status(),
            "beta": {
                "status": "ONLINE_ASSISTANT_1_3_BETA_READINESS_READY",
                "audit_count": len(audits),
                "latest_audit_status": str(latest_audit.get("status", "NOT_RUN")),
                "gates_passed": int(latest_audit.get("passed", 0) or 0),
                "gates_total": int(latest_audit.get("total", 12) or 12),
                "beta_ready": latest_confirmation.get("status") == "ONLINE_ASSISTANT_1_3_BETA_READY",
            },
            "safety": {
                "auto_approve": False, "writes_require_confirmation": True,
                "automatic_sending": False, "automatic_publication": False,
                "max_active_executions": 1,
            },
        }

    def _format_status(self) -> str:
        status = self.status()
        reliability = status["reliability"]
        beta = status["beta"]
        probe = dict(reliability.get("last_probe", {}) or {})
        return (
            "B131–B135 ONLINE ASSISTANT 1.3 BETA\n"
            f"B131 sesja: {probe.get('status', 'NOT_CHECKED')}; offline {'TAK' if reliability['offline_mode'] else 'NIE'}\n"
            f"B132 Gmail workflows: {status['gmail']['operation_count']} operacji\n"
            f"B133 Kalendarz: {status['calendar']['latest_event_count']} wydarzeń, {status['calendar']['latest_conflict_count']} konfliktów\n"
            f"B134 Dokumenty: {status['drive']['document_version_count']} wersji\n"
            f"B135 audyt: {beta['latest_audit_status']} {beta['gates_passed']}/{beta['gates_total']}\n"
            f"Beta: {'GOTOWA' if beta['beta_ready'] else 'OCZEKUJE'}; automatyczna wysyłka NIE."
        )

    @staticmethod
    def _format_gmail(result: dict[str, Any]) -> str:
        messages = list(result.get("messages", []) or [])
        lines = [
            f"B132 SKRZYNKA PRACY GMAIL ({result.get('mode')}): {len(messages)}",
            f"Nieprzeczytane: {result.get('unread_count', 0)}; ważne: {result.get('important_count', 0)}",
        ]
        for index, item in enumerate(messages[:8], start=1):
            lines.append(
                f"{index}. [{item.get('priority_score', 0)}] {clip(item.get('subject'), 100)} — "
                f"{clip(item.get('from'), 80)} | id={item.get('id')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_week(result: dict[str, Any]) -> str:
        lines = [
            f"B133 PLAN TYGODNIA ({result.get('mode')}): {result.get('event_count', 0)} wydarzeń; "
            f"konflikty {result.get('conflict_count', 0)}"
        ]
        for index, item in enumerate(list(result.get("events", []) or [])[:12], start=1):
            lines.append(f"{index}. {clip(item.get('start_at'), 32)} — {clip(item.get('title'), 110)}")
        return "\n".join(lines)

    @staticmethod
    def _format_slots(result: dict[str, Any]) -> str:
        slots = list(result.get("slots", []) or [])
        lines = [f"B133 PROPONOWANE TERMINY: {len(slots)}; czas {result.get('duration_minutes')} min"]
        lines.extend(f"{index}. {slot.get('start_at')}" for index, slot in enumerate(slots, start=1))
        return "\n".join(lines)

    @staticmethod
    def _format_drive(result: dict[str, Any], query: str) -> str:
        files = list(result.get("files", []) or [])
        lines = [f"B134 DOKUMENTY dla „{query}” ({result.get('mode')}): {len(files)}"]
        lines.extend(
            f"{index}. {clip(item.get('name'), 120)} | id={item.get('id')} | {clip(item.get('mime_type'), 60)}"
            for index, item in enumerate(files[:12], start=1)
        )
        return "\n".join(lines)

    @staticmethod
    def _format_versions(versions: list[dict[str, Any]]) -> str:
        if not versions:
            return "B134: brak dokumentów wersjonowanych przez JARVIS OS."
        lines = [f"B134 WERSJE DOKUMENTÓW: {len(versions)}"]
        lines.extend(
            f"{index}. {row.get('title')} v{row.get('version')} — {row.get('name')}"
            for index, row in enumerate(versions[-20:], start=1)
        )
        return "\n".join(lines)

    @staticmethod
    def _draft_slots(text: str) -> tuple[str, str, str]:
        match = re.search(
            r"(?i)(?:utw[oó]rz|przygotuj)\s+szkic\s+(?:gmail\s+1\.3|workflow\s+gmail)\s+do\s+(?P<to>\S+@\S+)\s+temat\s+(?P<subject>.+?)\s+tre[sś][cć]\s+(?P<body>.+)$",
            text,
        )
        if not match:
            raise ValueError("B132: użyj: Utwórz szkic Gmail 1.3 do adres@example.com temat TEMAT treść WIADOMOŚĆ.")
        return match.group("to"), match.group("subject").strip(), match.group("body").strip()

    @staticmethod
    def _label_slots(text: str) -> tuple[str, str]:
        match = re.search(
            r"(?i)(?:dodaj\s+etykiet[eę]\s+gmail|etykieta\s+gmail|oznacz\s+gmail\s+etykieta)\s+(?P<id>\S+)\s+(?:nazwa\s+|etykieta\s+)?(?P<label>.+)$",
            text,
        )
        if not match:
            raise ValueError("B132: użyj: Dodaj etykietę Gmail MESSAGE_ID nazwa ETYKIETA.")
        return match.group("id"), match.group("label").strip()

    @staticmethod
    def _calendar_slots(text: str) -> tuple[str, datetime, int]:
        match = re.search(
            r"(?i)(?:utw[oó]rz\s+wydarzenie|dodaj\s+spotkanie)\s+google\s+1\.3\s+(?P<title>.+?)\s+na\s+(?P<when>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})(?:\s+czas\s+(?P<duration>\d+))?$",
            text,
        )
        if not match:
            raise ValueError("B133: użyj: Utwórz wydarzenie Google 1.3 NAZWA na 2026-07-20 09:00 czas 30.")
        return (
            match.group("title").strip(),
            datetime.fromisoformat(match.group("when").replace(" ", "T")).astimezone(),
            max(5, min(int(match.group("duration") or 30), 1440)),
        )

    @staticmethod
    def _summary_slots(text: str) -> tuple[str, str, str]:
        match = re.search(
            r"(?i)podsumuj\s+dokument(?:\s+online|\s+1\.3)\s+id\s+(?P<id>\S+)\s+typ\s+(?P<mime>\S+)(?:\s+nazwa\s+(?P<name>.+))?$",
            text,
        )
        if not match:
            raise ValueError("B134: użyj: Podsumuj dokument online id PLIK_ID typ MIME_TYPE nazwa NAZWA.")
        return match.group("id"), match.group("mime"), (match.group("name") or "").strip()

    @staticmethod
    def _document_slots(text: str) -> tuple[str, str]:
        match = re.search(
            r"(?i)(?:utw[oó]rz|zapisz)\s+dokument\s+online\s+1\.3\s+nazwa\s+(?P<title>.+?)\s+tre[sś][cć]\s+(?P<body>.+)$",
            text,
        )
        if not match:
            raise ValueError("B134: użyj: Utwórz dokument online 1.3 nazwa NAZWA treść TREŚĆ.")
        return match.group("title").strip(), match.group("body").strip()

    @staticmethod
    def _duration(text: str) -> int:
        match = re.search(r"(?i)czas\s+(\d+)", text)
        return max(15, min(int(match.group(1)) if match else 30, 240))

    @staticmethod
    def _tail(text: str, prefixes: tuple[str, ...]) -> str:
        folded = fold_text(text)
        for prefix in prefixes:
            index = folded.find(prefix)
            if index >= 0:
                value = str(text)[index + len(prefix):].strip(" :.-")
                if value:
                    return value
        raise ValueError("B131–B134: brakuje parametru polecenia.")

    @staticmethod
    def _gate(name: str, passed: bool) -> dict[str, Any]:
        return {"name": str(name), "passed": bool(passed)}

    def _load_beta(self) -> dict[str, Any]:
        data = self.beta_store.load()
        return data if isinstance(data, dict) else {
            "version": "1.3-beta", "audits": [], "confirmations": [], "updated_at": "",
        }

    def _export(self, audit: dict[str, Any], confirmation: dict[str, Any]) -> None:
        destination = self.project_root / "AI_PLIKI" / "reports"
        destination.mkdir(parents=True, exist_ok=True)
        payload = {
            "product": "JARVIS OS Online Assistant 1.3 Beta",
            "audit": audit, "confirmation": confirmation,
            "safety": self.status()["safety"],
        }
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (destination / f"JARVIS_ONLINE_ASSISTANT_1_3_BETA_{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
