from __future__ import annotations

from datetime import datetime, timedelta
from email.utils import parseaddr
import re
from typing import Any

from app.natural_actions.active_resolution_analysis import ActiveIssueAnalyzer
from app.natural_actions.active_resolution_memory import ActiveResolutionMemory
from app.natural_actions.calendar_plan_guard import CalendarMovePlanGuard
from app.natural_actions.calendar_result_verifier import CalendarLiveResultVerifier
from app.natural_actions.calendar_safe_retry import CalendarSafeMoveExecutor
from app.natural_actions.calendar_undo import CalendarUndoCoordinator
from app.natural_actions.exact_conflict_proposal import ExactConflictProposal
from app.natural_actions.models import NaturalActionRequest
from app.natural_actions.startup_conflict_reactivation import reactivate_after_verified_undo


class ActiveResolutionService:
    """B166-B170 detect, propose, confirm, execute and verify."""

    INTENTS = {
        "active_conflict_advice", "active_conflict_move",
        "active_apply_suggestion", "active_mail_reply",
        "active_snooze", "active_ignore", "active_mark_done",
        "active_undo_calendar",
    }
    READ_ONLY = {"active_conflict_advice"}

    def __init__(
        self,
        context: Any,
        online: Any,
        daily: Any,
        proactive: Any,
        formatter: Any,
    ) -> None:
        self.context = context
        self.online = online
        self.proactive = proactive
        self.formatter = formatter
        self.analyzer = ActiveIssueAnalyzer(daily)
        project_root = getattr(online, "project_root", None)
        if project_root is None and hasattr(context, "store"):
            project_root = context.store.path.parents[2]
        self.memory = ActiveResolutionMemory(project_root)
        self.plan_guard = CalendarMovePlanGuard(
            online.calendar, self.analyzer, self.memory.clear_suggestion
        )
        self.result_verifier = CalendarLiveResultVerifier(
            online.calendar, self.analyzer
        )
        self.move_executor = CalendarSafeMoveExecutor(
            project_root, online.calendar, self.analyzer, self.plan_guard,
            self.result_verifier, self.memory.clear_suggestion,
        )
        self.exact_proposal = ExactConflictProposal(online.calendar, self.analyzer)
        self.undo = CalendarUndoCoordinator(
            context, online.calendar, self.analyzer, self.result_verifier,
            self.move_executor.ledger, formatter,
        )

    def prepare(self, request: NaturalActionRequest) -> None:
        handlers = {
            "active_conflict_advice": self._prepare_advice,
            "active_conflict_move": self._prepare_conflict_move,
            "active_apply_suggestion": self._prepare_apply,
            "active_mail_reply": self._prepare_mail_reply,
            "active_snooze": self._prepare_snooze,
            "active_ignore": lambda value: self._prepare_decision(
                value, "Pominąć ten alert do czasu zmiany sytuacji?"
            ),
            "active_undo_calendar": self.undo.prepare,
            "active_mark_done": lambda value: self._prepare_decision(
                value,
                "Oznaczyć ten alert jako obsłużony? "
                "Nie zmieni to kalendarza ani poczty.",
            ),
        }
        handlers[request.intent](request)

    def execute(self, request: NaturalActionRequest) -> str:
        if request.intent in {"active_conflict_move", "active_apply_suggestion"}:
            request.slots["request_fingerprint"] = self.formatter.fingerprint(request)
        handlers = {
            "active_conflict_advice": self._advice,
            "active_conflict_move": lambda value: self._move(dict(value.slots)),
            "active_apply_suggestion": self._apply_suggestion,
            "active_mail_reply": self._create_reply_draft,
            "active_snooze": self._snooze,
            "active_ignore": self._ignore,
            "active_mark_done": self._mark_done,
            "active_undo_calendar": self.undo.execute,
        }
        return handlers[request.intent](request)

    def filter_brief(self, result: dict[str, Any]) -> dict[str, Any]:
        filtered = dict(result or {})
        issue = dict(filtered.get("conflict_context", {}) or {}) or self.analyzer.current_issue()
        if not issue:
            return filtered
        if filtered.get("should_show") and not issue.get("alert_context"):
            self.memory.remember_issue(issue)
        decision = self.memory.decision(str(issue.get("fingerprint", "")))
        action = reactivate_after_verified_undo(
            self, issue, str(decision.get("action", "")), filtered
        )
        now = datetime.now().astimezone()
        if action in {"ignored", "completed"}:
            filtered["should_show"] = False
        elif action == "snoozed":
            until = self.analyzer.dt(decision.get("until"))
            if until is not None and now < until:
                filtered["should_show"] = False
            elif not decision.get("delivered_at"):
                filtered["should_show"] = True
                filtered["message"] = "Przypomnienie: " + str(
                    filtered.get("message", "")
                )
                self.memory.mark_delivered(issue["fingerprint"])
            else:
                filtered["should_show"] = False
        return filtered

    def status(self) -> dict[str, Any]:
        data = self.memory.load()
        return {
            "status": "ACTIVE_RESOLUTION_READY",
            "last_issue_type": str(
                dict(data.get("last_issue", {}) or {}).get("type", "")
            ),
            "has_suggestion": bool(data.get("last_suggestion")),
            "writes_require_confirmation": True,
            "automatic_calendar_changes": False,
            "automatic_mail_sending": False,
            "duplicate_protection": True,
            "safe_retry_limit": 1,
            "safe_undo": True,
        }

    def _prepare_advice(self, request: NaturalActionRequest) -> None:
        issue = self._conflict_issue()
        if not issue:
            self._missing(request, "conflict", "Nie widzę teraz konfliktu w kalendarzu.")
            return
        request.slots["issue"] = issue
        request.missing = []
        request.read_only = True

    def _prepare_conflict_move(self, request: NaturalActionRequest) -> None:
        issue = self._conflict_issue()
        if not issue:
            self._missing(
                request, "conflict",
                "Nie widzę teraz konfliktu, który mógłbym rozwiązać.",
            )
            return
        self.memory.remember_issue(issue)
        selector = str(request.slots.get("event_selector", "second") or "second")
        event = dict(issue.get(selector, {}) or {})
        request.slots.update(self.analyzer.event_slots(event, issue))
        if not request.slots.get("new_when"):
            self._missing(
                request, "new_when",
                f"Na którą godzinę mam przenieść „{event.get('title', 'wydarzenie')}”?",
            )
            return
        request.missing = []
        request.confirmation = (
            f"Przenieść „{event.get('title', 'wydarzenie')}” na "
            f"{self._display(request.slots['new_when'])}?"
        )

    def _prepare_apply(self, request: NaturalActionRequest) -> None:
        suggestion = self.memory.last_suggestion()
        if not suggestion:
            self._missing(
                request, "suggestion",
                "Nie mam teraz przygotowanej propozycji do wykonania.",
            )
            return
        request.slots.update(suggestion)
        request.missing = []
        request.confirmation = str(suggestion.get("confirmation", "")) or (
            "Wykonać przygotowaną propozycję?"
        )

    def _prepare_mail_reply(self, request: NaturalActionRequest) -> None:
        issue = self.analyzer.top_mail_issue()
        if not issue:
            self._missing(
                request, "mail",
                "Nie widzę wiadomości, na którą mam odpowiedzieć.",
            )
            return
        sender = str(issue.get("from", ""))
        name, address = parseaddr(sender)
        if not re.fullmatch(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", address):
            match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", sender)
            address = match.group(0) if match else ""
            name = sender.replace(address, "").strip(" <>-(),")
        body = self.analyzer.clean(request.slots.get("body"))
        if not address or "@" not in address:
            self._missing(
                request, "recipient_email",
                "Nie udało mi się odczytać adresu nadawcy tej wiadomości.",
            )
            return
        request.slots.update({
            "issue": issue,
            "recipient_ref": name or address,
            "recipient_email": address,
            "subject": self._reply_subject(issue.get("subject")),
        })
        if not body:
            self._missing(request, "body", "Co mam napisać w odpowiedzi?")
            return
        request.slots["body"] = body
        request.missing = []
        request.confirmation = (
            f"Przygotować szkic odpowiedzi do {name or address} "
            f"z tematem „{request.slots['subject']}”?"
        )

    def _prepare_snooze(self, request: NaturalActionRequest) -> None:
        issue = self._last_or_current_issue()
        if not issue:
            self._missing(
                request, "issue",
                "Nie mam teraz sprawy, którą mógłbym odłożyć.",
            )
            return
        minutes = max(5, min(int(request.slots.get("snooze_minutes", 60)), 10080))
        request.slots.update({"issue": issue, "snooze_minutes": minutes})
        request.missing = []
        request.confirmation = (
            f"Przypomnieć o tej sprawie za {self.formatter.minutes(minutes)}?"
        )

    def _prepare_decision(
        self,
        request: NaturalActionRequest,
        confirmation: str,
    ) -> None:
        issue = self._last_or_current_issue()
        if not issue:
            self._missing(
                request, "issue",
                "Nie mam teraz aktywnej sprawy do oznaczenia.",
            )
            return
        request.slots["issue"] = issue
        request.missing = []
        request.confirmation = confirmation

    def _advice(self, request: NaturalActionRequest) -> str:
        issue = dict(request.slots["issue"])
        suggestion = self.exact_proposal.build(issue)
        suggestion["confirmation"] = (
            f"Przenieść „{suggestion['event_title']}” na "
            f"{self._display(suggestion['new_when'])}?"
        )
        self.memory.remember_issue(issue)
        self.memory.remember_suggestion(suggestion)
        return (
            f"Najprościej przenieść „{suggestion['event_title']}” na "
            f"{self._display(suggestion['new_when'])}. Zachowam czas trwania. "
            "Powiedz „zrób to”, a pokażę potwierdzenie przed zmianą."
        )

    def _apply_suggestion(self, request: NaturalActionRequest) -> str:
        slots = dict(request.slots)
        if str(slots.get("kind", "")) != "calendar_move":
            raise ValueError("Ta propozycja nie ma bezpiecznego wykonawcy.")
        response = self._move(slots)
        self.memory.clear_suggestion()
        return response

    def _move(self, slots: dict[str, Any]) -> str:
        new_when = self.analyzer.dt(slots.get("new_when"))
        if new_when is None:
            raise ValueError("Brakuje poprawnego nowego terminu wydarzenia.")
        duration = max(5, min(int(slots.get("duration_minutes", 60)), 1440))
        event_id = str(slots.get("event_id", "")).strip()
        outcome = self.move_executor.execute(slots, new_when, duration)
        live = outcome.live
        actual = self.analyzer.dt(live.get("start_at"))
        fingerprint = str(slots.get("issue_fingerprint", ""))
        if fingerprint:
            self.memory.decide(fingerprint, "completed")
        if outcome.duplicate:
            return (
                "Ta zmiana została już wykonana. "
                f"„{slots['event_title']}” jest {self.formatter.when(actual)}. "
                "Sprawdziłem termin w Google Calendar."
            )
        return (
            f"Przeniosłem „{slots['event_title']}” na "
            f"{self.formatter.when(actual)}. Sprawdziłem nowy termin w Google Calendar."
        )

    def _create_reply_draft(self, request: NaturalActionRequest) -> str:
        slots = request.slots
        result = self.online.gmail.create_draft(
            slots["recipient_email"], slots["subject"], slots["body"]
        )
        slots["draft_id"] = str(result.get("draft_id", ""))
        return (
            f"Szkic odpowiedzi do {slots['recipient_ref']} jest gotowy. "
            "Wiadomość nie została wysłana."
        )

    def _snooze(self, request: NaturalActionRequest) -> str:
        issue = dict(request.slots["issue"])
        minutes = int(request.slots["snooze_minutes"])
        until = datetime.now().astimezone() + timedelta(minutes=minutes)
        self.memory.decide(issue["fingerprint"], "snoozed", until=until)
        return f"Przypomnę o tej sprawie za {self.formatter.minutes(minutes)}."

    def _ignore(self, request: NaturalActionRequest) -> str:
        issue = dict(request.slots["issue"])
        self.memory.decide(issue["fingerprint"], "ignored")
        return "Pominąłem ten alert. Pokażę go ponownie, jeśli sytuacja się zmieni."

    def _mark_done(self, request: NaturalActionRequest) -> str:
        issue = dict(request.slots["issue"])
        self.memory.decide(issue["fingerprint"], "completed")
        return (
            "Oznaczyłem alert jako obsłużony. "
            "Nie zmieniłem kalendarza ani poczty."
        )

    def _conflict_issue(self) -> dict[str, Any]:
        last = self.memory.last_issue()
        if last.get("type") == "conflict" and last.get("alert_context"):
            return last
        current = self.analyzer.conflict_issue()
        return current or (last if last.get("type") == "conflict" else {})

    def _last_or_current_issue(self) -> dict[str, Any]:
        return self.memory.last_issue() or self.analyzer.current_issue()

    @staticmethod
    def _reply_subject(value: object) -> str:
        subject = " ".join(str(value or "wiadomość").split()).strip()
        return subject if subject.casefold().startswith("re:") else "Re: " + subject

    def _display(self, value: object) -> str:
        parsed = self.analyzer.dt(value)
        return parsed.strftime("%d.%m.%Y o %H:%M") if parsed else "nieznany termin"

    @staticmethod
    def _missing(
        request: NaturalActionRequest,
        name: str,
        message: str,
    ) -> None:
        request.missing = [name]
        request.clarification = message
