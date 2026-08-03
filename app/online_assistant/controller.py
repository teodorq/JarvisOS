from __future__ import annotations
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any, Callable
from uuid import uuid4

from app.assistant.natural_language import fold_text
from app.assistant_v12.controller import AssistantV12Controller
from app.assistant_v12.context_hub import utc_now
from app.assistant_v12.progress_runtime import AssistantProgressRuntime
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.calendar_center import GoogleCalendarCenter
from app.online_assistant.common import OnlineAssistantError, clip
from app.online_assistant.day_center import OnlineDayCenter
from app.online_assistant.drive_center import GoogleDriveCenter
from app.online_assistant.gmail_center import GmailOnlineCenter
from app.online_assistant.google_workspace import GoogleWorkspaceProvider
from app.online_assistant_v13.controller import OnlineAssistantV13Controller
from app.productivity.reminder_center import ReminderCenterV2

class OnlineAssistantController:
    """B126-B130 explicit-consent Google Workspace assistant and Stable RC gates."""

    STAGES = {
        "B126": "REAL_GMAIL_CENTER_READY",
        "B127": "REAL_GOOGLE_CALENDAR_READY",
        "B128": "REAL_GOOGLE_DRIVE_READY",
        "B129": "ONLINE_DAY_CENTER_READY",
        "B130": "BUSINESS_1_2_STABLE_RC_READINESS_READY",
        **OnlineAssistantV13Controller.STAGES,
    }
    READ_ONLY_INTENTS = {
        "online_status",
        "gmail_latest",
        "gmail_priority",
        "calendar_today",
        "calendar_conflicts",
        "drive_search",
        "drive_summarize",
        "day_overview",
        "rc_audit",
    }
    WRITE_INTENTS = {
        "google_connect",
        "google_disconnect",
        "gmail_create_draft",
        "gmail_send_draft",
        "calendar_create",
        "drive_create_report",
        "rc_confirm",
    }

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        provider: Any | None = None,
        reminders: Any | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider or GoogleWorkspaceProvider(self.project_root)
        self.gmail = GmailOnlineCenter(self.project_root, provider=self.provider)
        self.calendar = GoogleCalendarCenter(self.project_root, provider=self.provider)
        self.drive = GoogleDriveCenter(self.project_root, provider=self.provider)
        self.reminders = reminders or ReminderCenterV2(self.project_root)
        self.day = OnlineDayCenter(
            self.project_root,
            gmail=self.gmail,
            calendar=self.calendar,
            drive=self.drive,
            reminders=self.reminders,
        )
        self.progress = AssistantProgressRuntime(self.project_root)
        self.v13 = OnlineAssistantV13Controller(
            self.project_root, provider=self.provider, previous=self
        )
        self.rc_store = JsonStore(
            self.project_root / "data" / "online_assistant" / "business_1_2_stable_rc.json",
            lambda: {"version": "1.2-rc", "audits": [], "confirmations": [], "updated_at": ""},
        )

    def set_progress_callback(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self.progress.set_callback(callback)
        self.v13.set_progress_callback(callback)

    @staticmethod
    def matches(command: object) -> bool:
        text = fold_text(command)
        phrases = (
            "asystent online",
            "google workspace",
            "polacz google",
            "rozlacz google",
            "status google",
            "gmail",
            "kalendarz google",
            "dysk google",
            "google drive",
            "centrum dnia online",
            "business 1.2 stable rc",
            "audyt rc",
            "potwierdz rc",
            "b126",
            "b127",
            "b128",
            "b129",
            "b130",
        )
        return any(phrase in text for phrase in phrases) or OnlineAssistantV13Controller.matches(command)

    def intent(self, command: object) -> str:
        text = fold_text(command)
        rules = (
            ("google_disconnect", ("rozlacz google", "usun polaczenie google")),
            ("google_connect", ("polacz google", "autoryzuj google", "zaloguj google")),
            (
                "rc_confirm",
                (
                    "potwierdz business 1.2 stable rc",
                    "potwierdz stable rc",
                    "potwierdz rc b130",
                    "potwierdz b130",
                ),
            ),
            (
                "rc_audit",
                (
                    "uruchom audyt business 1.2 stable rc",
                    "uruchom test business 1.2 stable rc",
                    "audyt business 1.2 stable rc",
                    "test business 1.2 stable rc",
                    "sprawdz business 1.2 stable rc",
                    "uruchom audyt b130",
                    "audyt b130",
                    "audyt rc",
                ),
            ),
            ("gmail_send_draft", ("wyslij szkic gmail", "wyslij draft gmail")),
            ("gmail_create_draft", ("utworz szkic gmail", "przygotuj szkic gmail")),
            ("gmail_priority", ("priorytetowe maile gmail", "wazne maile gmail", "pilne maile gmail")),
            ("gmail_latest", ("najnowsze maile gmail", "pokaz maile gmail", "skrzynka gmail")),
            ("calendar_create", ("dodaj wydarzenie google", "utworz wydarzenie google", "dodaj spotkanie google")),
            ("calendar_conflicts", ("konflikty kalendarza google", "sprawdz konflikty google")),
            ("calendar_today", ("kalendarz google na dzis", "dzisiejszy kalendarz google", "pokaz kalendarz google")),
            ("drive_create_report", ("zapisz raport na dysku google", "utworz raport na google drive")),
            ("drive_summarize", ("podsumuj dokument z dysku google", "podsumuj plik google drive")),
            ("drive_search", ("wyszukaj na dysku google", "znajdz na google drive", "szukaj google drive")),
            ("day_overview", ("centrum dnia online", "moj dzien online", "pokaz dzien online")),
            ("online_status", ("status asystenta online", "status google workspace", "status b126", "status b130")),
        )
        for intent, phrases in rules:
            if any(phrase in text for phrase in phrases):
                return intent
        return "online_status"

    def plan(self, command: object) -> dict[str, Any]:
        if self.v13.matches(command):
            return self.v13.plan(command)
        intent = self.intent(command)
        return {
            "command": str(command).strip(),
            "goal": "Obsłużyć Google Workspace przez JARVIS OS 1.2 Stable RC",
            "plan": [
                "Rozpoznać usługę Gmail, Kalendarz, Dysk albo Centrum Dnia",
                "Sprawdzić lokalny stan OAuth i minimalne wymagane uprawnienia",
                "Wymagać potwierdzenia przed połączeniem, zapisem lub wysyłką",
                "Wykonać jedną ograniczoną operację i pokazać rzeczywisty postęp",
                "Zapisać lokalny audyt bez ujawniania tokenów i danych uwierzytelniających",
            ],
            "actions": [],
            "can_execute": True,
            "handler": "personal_assistant",
            "assistant_intent": intent,
            "read_only": intent in self.READ_ONLY_INTENTS,
            "online_operation": True,
            "requires_confirmation": intent in self.WRITE_INTENTS,
        }

    def handle(self, command: object) -> str:
        if self.v13.matches(command):
            return self.v13.handle(command)
        text = str(command).strip()
        intent = self.intent(text)
        self.progress.start(command=text, intent=intent)
        try:
            self.progress.phase("POŁĄCZENIE", 20, "Sprawdzam lokalny OAuth i gotowość Google Workspace.")
            if intent == "online_status":
                response = self._format_status()
            elif intent == "google_connect":
                self.progress.phase("AUTORYZACJA", 45, "Otwieram zgodę Google w przeglądarce.")
                result = self.provider.connect()
                response = (
                    "B126–B128: Google Workspace połączony. "
                    f"Gmail {'OK' if result['gmail'] else 'BŁĄD'}, "
                    f"Kalendarz {'OK' if result['calendar'] else 'BŁĄD'}, "
                    f"Dysk {'OK' if result['drive'] else 'BŁĄD'}."
                )
            elif intent == "google_disconnect":
                result = self.provider.disconnect()
                response = f"B126: {result['status']}; lokalny token usunięty {'TAK' if result['token_removed'] else 'NIE'}."
            elif intent == "gmail_latest":
                self.progress.phase("GMAIL", 55, "Pobieram najnowsze wiadomości bez modyfikacji skrzynki.")
                response = self._format_mail(self.gmail.latest(10), "Najnowsze wiadomości Gmail")
            elif intent == "gmail_priority":
                self.progress.phase("GMAIL", 55, "Pobieram priorytetowe wiadomości bez oznaczania ich jako przeczytane.")
                response = self._format_mail(self.gmail.priority(10), "Priorytetowe wiadomości Gmail")
            elif intent == "gmail_create_draft":
                recipient, subject, body = self._gmail_draft_slots(text)
                result = self.gmail.create_draft(recipient, subject, body)
                response = (
                    f"B126: utworzono szkic Gmail {result['draft_id']} do {result['recipient']} "
                    f"z tematem „{result['subject']}”. Wiadomość nie została wysłana."
                )
            elif intent == "gmail_send_draft":
                draft_id = self._tail(text, ("wyslij szkic gmail", "wyslij draft gmail"))
                result = self.gmail.send_draft(draft_id)
                response = f"B126: szkic Gmail wysłany po potwierdzeniu; message_id {result['message_id']}."
            elif intent == "calendar_today":
                self.progress.phase("KALENDARZ", 55, "Pobieram dzisiejszy plan z Kalendarza Google.")
                response = self._format_events(self.calendar.today(), "Dzisiejszy Kalendarz Google")
            elif intent == "calendar_conflicts":
                conflicts = self.calendar.conflicts()
                response = self._format_conflicts(conflicts)
            elif intent == "calendar_create":
                title, when, duration = self._calendar_slots(text)
                result = self.calendar.create_event(title, when, duration_minutes=duration)
                response = f"B127: utworzono wydarzenie „{result['title']}” na {result['start_at']}."
            elif intent == "drive_search":
                query = self._tail(text, ("wyszukaj na dysku google", "znajdz na google drive", "szukaj google drive"))
                response = self._format_drive(self.drive.search(query), query)
            elif intent == "drive_summarize":
                file_id, mime_type, name = self._drive_summary_slots(text)
                result = self.drive.summarize(file_id, mime_type, name=name)
                response = f"B128: podsumowanie „{result['name'] or result['file_id']}”: {result['summary']}"
            elif intent == "drive_create_report":
                name = f"JARVIS_DAY_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                snapshot = self.day.snapshot()
                content = self.day.format_snapshot(snapshot)
                result = self.drive.create_report(name, content)
                response = f"B128: raport zapisany na Dysku Google jako „{result['name']}”."
            elif intent == "day_overview":
                self.progress.phase("CENTRUM DNIA", 60, "Łączę Gmail, Kalendarz Google i lokalne przypomnienia.")
                response = self.day.format_snapshot(self.day.snapshot())
            elif intent == "rc_audit":
                audit = self.run_rc_audit()
                response = f"B130: audyt {audit['status']}; bramki {audit['passed']}/{audit['total']}."
            elif intent == "rc_confirm":
                response = self.confirm_rc()["status"]
            else:
                raise OnlineAssistantError("B126–B130: nie rozpoznano polecenia online.")
            self.progress.phase("WERYFIKACJA", 92, "Weryfikuję wynik i zapisuję lokalny ślad bez tokenów.")
            self.progress.complete(response)
            return response
        except Exception as error:
            self.progress.fail(error)
            if isinstance(error, (OnlineAssistantError, ValueError)):
                raise ValueError(str(error)) from None
            raise

    def run_rc_audit(self) -> dict[str, Any]:
        connection = self.provider.connection_status()
        beta_ready = AssistantV12Controller(self.project_root).status()["beta"]["beta_ready"]
        probes = {"gmail": False, "calendar": False, "drive": False}
        if connection["dependency_ready"] and connection["client_configured"] and connection["token_present"]:
            try:
                probes = self.provider.live_probe()
            except OnlineAssistantError:
                probes = {"gmail": False, "calendar": False, "drive": False}
        gates = [
            self._gate("BUSINESS_1_2_BETA_READY", bool(beta_ready)),
            self._gate("GOOGLE_DEPENDENCIES_READY", bool(connection["dependency_ready"])),
            self._gate("OAUTH_DESKTOP_CLIENT_CONFIGURED", bool(connection["client_configured"])),
            self._gate("LOCAL_TOKEN_PRESENT", bool(connection["token_present"])),
            self._gate("LIVE_GMAIL_READ", bool(probes["gmail"])),
            self._gate("LIVE_CALENDAR_READ", bool(probes["calendar"])),
            self._gate("LIVE_DRIVE_READ", bool(probes["drive"])),
            self._gate("WRITE_CONFIRMATION_REQUIRED", True),
            self._gate("AUTOMATIC_SENDING_OFF", True),
            self._gate("AUTOMATIC_PUBLICATION_OFF", True),
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
        data = self._rc_load()
        audits = list(data.get("audits", []) or [])
        audits.append(audit)
        data.update({"audits": audits[-30:], "updated_at": utc_now()})
        self.rc_store.save(data)
        return audit

    def confirm_rc(self) -> dict[str, Any]:
        data = self._rc_load()
        audits = list(data.get("audits", []) or [])
        if not audits or audits[-1].get("status") != "PASSED":
            raise ValueError(
                "B130: najpierw połącz Google Workspace i uruchom zaliczony audyt Stable RC."
            )
        confirmation = {
            "confirmation_id": uuid4().hex[:16],
            "audit_id": audits[-1]["audit_id"],
            "status": "BUSINESS_1_2_STABLE_RC_READY",
            "confirmed_at": utc_now(),
            "automatic_publication": False,
            "automatic_sending": False,
            "owner_mode_preserved": True,
        }
        confirmations = list(data.get("confirmations", []) or [])
        confirmations.append(confirmation)
        data.update({"confirmations": confirmations[-20:], "updated_at": utc_now()})
        self.rc_store.save(data)
        self._export_rc(audits[-1], confirmation)
        return confirmation

    def status(self) -> dict[str, Any]:
        connection = self.provider.connection_status()
        data = self._rc_load()
        audits = list(data.get("audits", []) or [])
        confirmations = list(data.get("confirmations", []) or [])
        latest_audit = dict(audits[-1]) if audits else {}
        latest_confirmation = dict(confirmations[-1]) if confirmations else {}
        return {
            "status": "REAL_ONLINE_ASSISTANT_RC_READY",
            "stages": dict(self.STAGES),
            "connection": connection,
            "gmail": self.gmail.status(),
            "calendar": self.calendar.status(),
            "drive": self.drive.status(),
            "day_center": self.day.status(),
            "progress": self.progress.status(),
            "v13": self.v13.status(),
            "rc": {
                "status": "BUSINESS_1_2_STABLE_RC_READINESS_READY",
                "audit_count": len(audits),
                "latest_audit_status": str(latest_audit.get("status", "NOT_RUN")),
                "gates_passed": int(latest_audit.get("passed", 0) or 0),
                "gates_total": int(latest_audit.get("total", 10) or 10),
                "rc_ready": latest_confirmation.get("status") == "BUSINESS_1_2_STABLE_RC_READY",
                "automatic_publication": False,
            },
            "safety": {
                "auto_approve": False,
                "max_active_executions": 1,
                "writes_require_confirmation": True,
                "automatic_sending": False,
                "automatic_sync": False,
            },
        }

    def _format_status(self) -> str:
        value = self.status()
        connection = value["connection"]
        rc = value["rc"]
        missing = ", ".join(connection["missing_dependencies"][:3]) or "BRAK"
        return (
            "B126–B130 ASYSTENT ONLINE\n"
            f"Google Workspace: {connection['status']}\n"
            f"Biblioteki: {'GOTOWE' if connection['dependency_ready'] else 'BRAK'}; brakujące: {missing}\n"
            f"OAuth Desktop: {'GOTOWY' if connection['client_configured'] else 'BRAK PLIKU'}\n"
            f"Token lokalny: {'TAK' if connection['token_present'] else 'NIE'}\n"
            f"B130 audyt: {rc['latest_audit_status']} {rc['gates_passed']}/{rc['gates_total']}\n"
            f"Stable RC: {'GOTOWY' if rc['rc_ready'] else 'OCZEKUJE'}\n"
            "Bezpieczeństwo: zapis i wysyłka wymagają potwierdzenia; automatyczna wysyłka NIE."
        )

    @staticmethod
    def _format_mail(messages: list[dict[str, Any]], title: str) -> str:
        if not messages:
            return f"B126 {title}: brak wiadomości."
        lines = [f"B126 {title}: {len(messages)}"]
        for index, item in enumerate(messages[:8], start=1):
            flags = []
            if item.get("unread"):
                flags.append("NIEPRZECZYTANA")
            if item.get("important"):
                flags.append("WAŻNA")
            suffix = f" [{' / '.join(flags)}]" if flags else ""
            lines.append(
                f"{index}. {clip(item.get('subject') or '(bez tematu)', 100)} — "
                f"{clip(item.get('from') or 'nieznany nadawca', 90)}{suffix}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_events(events: list[dict[str, Any]], title: str) -> str:
        if not events:
            return f"B127 {title}: brak wydarzeń."
        lines = [f"B127 {title}: {len(events)}"]
        for index, item in enumerate(events[:12], start=1):
            lines.append(
                f"{index}. {clip(item.get('start_at'), 40)} — "
                f"{clip(item.get('title') or '(bez nazwy)', 120)}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_conflicts(conflicts: list[dict[str, Any]]) -> str:
        if not conflicts:
            return "B127: nie wykryto konfliktów w najbliższych 7 dniach."
        lines = [f"B127: konflikty Kalendarza Google: {len(conflicts)}"]
        for index, conflict in enumerate(conflicts[:10], start=1):
            left = dict(conflict.get("left", {}) or {})
            right = dict(conflict.get("right", {}) or {})
            lines.append(
                f"{index}. „{clip(left.get('title'), 70)}” koliduje z „{clip(right.get('title'), 70)}”."
            )
        return "\n".join(lines)

    @staticmethod
    def _format_drive(results: list[dict[str, Any]], query: str) -> str:
        if not results:
            return f"B128: brak wyników na Dysku Google dla „{query}”."
        lines = [f"B128: wyniki Dysku Google dla „{query}”: {len(results)}"]
        for index, item in enumerate(results[:12], start=1):
            lines.append(
                f"{index}. {clip(item.get('name'), 120)} | {clip(item.get('mime_type'), 80)} | id={item.get('id')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _gmail_draft_slots(text: str) -> tuple[str, str, str]:
        match = re.search(
            r"(?i)(?:utw[oó]rz|przygotuj)\s+szkic\s+gmail\s+do\s+(?P<to>\S+@\S+)\s+temat\s+(?P<subject>.+?)\s+tre[sś][cć]\s+(?P<body>.+)$",
            text,
        )
        if not match:
            raise ValueError(
                "B126: użyj: Utwórz szkic Gmail do adres@example.com temat TEMAT treść WIADOMOŚĆ."
            )
        return match.group("to"), match.group("subject").strip(), match.group("body").strip()

    @staticmethod
    def _calendar_slots(text: str) -> tuple[str, datetime, int]:
        match = re.search(
            r"(?i)(?:dodaj|utw[oó]rz)\s+(?:wydarzenie|spotkanie)\s+google\s+(?P<title>.+?)\s+na\s+(?P<when>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})(?:\s+czas\s+(?P<duration>\d+))?$",
            text,
        )
        if not match:
            raise ValueError(
                "B127: użyj: Dodaj wydarzenie Google NAZWA na 2026-07-20 09:00 czas 30."
            )
        when = datetime.fromisoformat(match.group("when").replace(" ", "T")).astimezone()
        duration = int(match.group("duration") or 30)
        return match.group("title").strip(), when, duration

    @staticmethod
    def _drive_summary_slots(text: str) -> tuple[str, str, str]:
        match = re.search(
            r"(?i)podsumuj\s+(?:dokument\s+z\s+dysku\s+google|plik\s+google\s+drive)\s+id\s+(?P<id>\S+)\s+typ\s+(?P<mime>\S+)(?:\s+nazwa\s+(?P<name>.+))?$",
            text,
        )
        if not match:
            raise ValueError(
                "B128: użyj: Podsumuj dokument z Dysku Google id PLIK_ID typ MIME_TYPE nazwa NAZWA."
            )
        return match.group("id"), match.group("mime"), (match.group("name") or "").strip()

    @staticmethod
    def _tail(text: str, prefixes: tuple[str, ...]) -> str:
        folded = fold_text(text)
        for prefix in prefixes:
            index = folded.find(prefix)
            if index >= 0:
                value = str(text)[index + len(prefix) :].strip(" :.-")
                if value:
                    return value
        raise ValueError("B126–B128: brakuje parametru polecenia.")

    @staticmethod
    def _gate(name: str, passed: bool) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed)}

    def _rc_load(self) -> dict[str, Any]:
        value = self.rc_store.load()
        if isinstance(value, dict):
            return value
        return {"version": "1.2-rc", "audits": [], "confirmations": [], "updated_at": ""}

    def _export_rc(self, audit: dict[str, Any], confirmation: dict[str, Any]) -> None:
        destination = self.project_root / "AI_PLIKI" / "reports"
        destination.mkdir(parents=True, exist_ok=True)
        payload = {
            "product": "JARVIS OS 1.2 Stable RC",
            "audit": audit,
            "confirmation": confirmation,
            "safety": self.status()["safety"],
        }
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        (destination / f"JARVIS_BUSINESS_1_2_STABLE_RC_{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
