from __future__ import annotations
from datetime import datetime, time
from pathlib import Path
from typing import Any
from app.assistant.natural_language import fold_text
from app.core.project_paths import resolve_project_root
from app.natural_actions.advanced_actions import AdvancedNaturalActions
from app.natural_actions.context import NaturalActionContext
from app.natural_actions.models import NaturalActionRequest
from app.natural_actions.proactive_conflict_brief_guard import ProactiveConflictBriefGuard
from app.natural_actions.recipients import RecipientResolver
from app.natural_actions.temporal import PolishTemporalParser
from app.natural_actions.runtime import NaturalActionRuntime
from app.natural_actions.understanding import NaturalActionUnderstanding
from app.natural_actions.validation import (
    clean_reference,
    is_placeholder,
    valid_email,
)
class NaturalActionService:
    """Natural mail/calendar actions with context, correction and safety."""
    STAGES = {
        "B141": "NATURAL_INTENT_UNDERSTANDING_READY",
        "B142": "UNIVERSAL_SLOT_EXTRACTION_READY",
        "B143": "GOOGLE_PRODUCTIVITY_ACTIONS_READY",
        "B144": "MULTI_TURN_CLARIFICATION_READY",
        "B145": "SURPRISE_GENERALIZATION_GATES_READY",
        "B146": "CONVERSATION_ACTION_MEMORY_READY",
        "B147": "CONTACT_RESOLUTION_AND_VALIDATION_READY",
        "B148": "NATURAL_CORRECTION_FLOW_READY",
        "B149": "ONE_INTENT_ONE_EXECUTION_READY",
        "B150": "PRACTICAL_SURPRISE_SUITE_READY",
        "B151": "CALENDAR_EVENT_MUTATION_READY",
        "B152": "CALENDAR_EVENT_SEARCH_READY",
        "B153": "CONFIRMED_EXISTING_DRAFT_SEND_READY",
        "B154": "CONTACT_ALIAS_CONTINUITY_READY",
        "B155": "DAILY_ACTION_SURPRISE_GATES_READY",
        "B156": "INTELLIGENT_DAY_OVERVIEW_READY",
        "B157": "TODAY_REACTION_PRIORITY_READY",
        "B158": "NATURAL_DAY_PLANNING_READY",
        "B159": "COMPLETION_MEMORY_READY",
        "B160": "DAILY_USEFULNESS_GATES_READY",
        "B161": "AUTOMATIC_DAILY_BRIEF_READY",
        "B162": "URGENT_SIGNAL_AND_CONFLICT_DETECTION_READY",
        "B163": "SELECTIVE_NOTIFICATION_POLICY_READY",
        "B164": "NEXT_BEST_ACTION_PROPOSALS_READY",
        "B165": "PROACTIVE_DAILY_USEFULNESS_GATES_READY",
        "B166": "ACTIVE_ISSUE_ADVICE_READY", "B167": "CONFIRMED_CONFLICT_RESOLUTION_READY",
        "B168": "IMPORTANT_MAIL_REPLY_DRAFT_READY", "B169": "SNOOZE_IGNORE_COMPLETE_READY",
        "B170": "DETECT_PROPOSE_EXECUTE_VERIFY_READY",
        "B171": "STALE_CALENDAR_PLAN_GUARD_READY", "B172": "LIVE_CALENDAR_RESULT_VERIFICATION_READY", "B173": "DUPLICATE_PROTECTION_SAFE_RETRY_READY", "B174": "SAFE_UNDO_LAST_CALENDAR_CHANGE_READY", "B175": "RELIABILITY_RELEASE_GATE_READY", "B176": "STARTUP_CONFLICT_SCAN_READY", "B177": "NEW_CHANGED_CONFLICT_NOTIFICATION_READY", "B178": "LIVE_CONFLICT_REFRESH_READY", "B178.1": "LIVE_REFRESH_FALLBACK_SUPPRESSION_READY", "B179": "SAFE_PROACTIVITY_POLICY_READY", "B180": "PROACTIVE_CALENDAR_RELIABILITY_GATE_READY", "B181": "EXACT_ALERT_CONFLICT_CONTEXT_READY", "B182": "EXACT_SAFE_CONFLICT_PROPOSAL_READY", "B186": "LIVE_GMAIL_SEARCH_READY", "B187": "FULL_GMAIL_THREAD_READ_READY", "B188": "THREADED_REPLY_DRAFT_READY", "B189": "CONFIRMED_VERIFIED_GMAIL_SEND_READY", "B190": "GMAIL_LIVE_RELIABILITY_GATE_READY", "B190.1": "GMAIL_WORKFLOW_QUALITY_CLOSURE_READY", "B190.2": "GMAIL_SEND_CONFIRMATION_BRIDGE_READY",
    }
    def __init__(
        self,
        project_root: str | Path | None,
        *,
        online: Any,
        now_provider: Any | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.online = online
        self.context = NaturalActionContext(self.project_root)
        self.temporal = PolishTemporalParser(now_provider)
        self.understanding = NaturalActionUnderstanding(self.temporal)
        self.recipients = RecipientResolver(self.project_root, online.provider)
        self.runtime = NaturalActionRuntime(self.context, online)
        self.advanced = AdvancedNaturalActions(self.context, online, self.runtime, self.temporal.now_provider)
    @staticmethod
    def matches(command: object) -> bool:
        intent, confidence = NaturalActionUnderstanding.classify(command)
        return intent != "standard" and confidence >= 0.7
    def has_pending(self) -> bool:
        return self.context.has_pending()
    def startup_conflict_scan(self) -> dict[str, Any]:
        return self.runtime.startup_notifications.filter(self.runtime.active.filter_brief(self.runtime.startup_conflicts.scan()))
    def startup_brief(self, *, force: bool = False) -> dict[str, Any]:
        result = self.runtime.proactive.startup_brief(force=force)
        return self.runtime.active.filter_brief(result)
    def proactive_brief_guard(self) -> dict[str, Any]:
        scan = self.runtime.startup_conflicts.scan()
        filtered = self.runtime.active.filter_brief(scan)
        return ProactiveConflictBriefGuard.evaluate(
            filtered,
            self.runtime.startup_notifications.status(),
        )
    def plan(self, command: object) -> dict[str, Any]:
        request = self._prepare(command)
        fingerprint = self.runtime.fingerprint(request) if request.complete else ""
        return {
            "command": request.command,
            "original_command": request.original,
            "goal": "Zrozumieć cel i bezpiecznie wykonać naturalne polecenie",
            "plan": [
                "Rozpoznać intencję i użyteczny kontekst rozmowy",
                "Wyciągnąć lub uzupełnić odbiorcę, treść, termin i przypomnienie",
                "Dopytać wyłącznie o brakujące albo niejednoznaczne dane",
                "Pokazać dokładny plan przed zapisem albo wysyłką",
                "Wykonać działanie jeden raz i potwierdzić rezultat",
            ],
            "actions": [],
            "can_execute": request.can_execute,
            "handler": "personal_assistant",
            "assistant_intent": request.intent,
            "read_only": request.read_only or bool(request.missing),
            "requires_confirmation": request.complete and not request.read_only,
            "confirmation_message": request.confirmation,
            "natural_action": True,
            "natural_slots": dict(request.slots),
            "clarification": request.clarification,
            "used_context": request.used_context,
            "operation_fingerprint": fingerprint,
        }
    def handle(self, command: object) -> str:
        request = self._prepare(command)
        if request.intent == "cancel":
            self.context.clear_pending()
            return "Anulowałem przygotowywane działanie."
        if request.intent == "standard":
            raise ValueError("Nie rozpoznałem jeszcze celu tego polecenia.")
        if request.missing:
            self.context.set_pending(
                intent=request.intent,
                slots=request.slots,
                missing=request.missing,
                prompt=request.clarification,
            )
            return request.clarification
        self.context.clear_pending()
        response = self.runtime.execute_once(request)
        self.context.remember(request, response)
        return response
    def status(self) -> dict[str, Any]:
        data = self.context.load()
        return {
            "status": "CONTEXTUAL_NATURAL_ACTIONS_READY",
            "stages": dict(self.STAGES),
            "pending": bool(self.context.pending()),
            "history_count": len(list(data.get("history", []) or [])),
            "known_references": len(dict(data.get("references", {}) or {})),
            "writes_require_confirmation": True,
            "automatic_sending": False,
            "proactive": self.runtime.proactive.status(),
            "startup_conflicts": self.runtime.startup_conflicts.status(),
            "startup_notifications": self.runtime.startup_notifications.status(),
            "proactive_brief_guard": ProactiveConflictBriefGuard.status(),
            "active_resolution": self.runtime.active.status(),
            "gmail_live": self.runtime.gmail_live.status(),
            "duplicate_window_seconds": int(self.context.EXECUTION_TTL.total_seconds()),
        }
    def _prepare(self, command: object) -> NaturalActionRequest:
        pending = self.context.pending()
        request = self.understanding.parse(command, pending=pending or None)
        self.runtime.gmail_live.adopt_selected_reply(request)
        if request.intent == "cancel":
            return request
        self._apply_context(request)
        if request.intent in self.runtime.gmail_live.INTENTS: self.runtime.gmail_live.prepare(request)
        elif request.intent in self.runtime.active.INTENTS:
            self.runtime.active.prepare(request)
        elif request.intent in self.advanced.INTENTS:
            self.advanced.prepare(request)
        elif request.intent.startswith("mail_"):
            self._prepare_mail(request)
        elif request.intent == "calendar_create":
            self._prepare_calendar(request)
        request.read_only = (
            bool(request.missing)
            or request.intent in {"standard", "cancel", "calendar_search"}
            or request.intent in self.runtime.daily.READ_ONLY | self.runtime.business.READ_ONLY
            or request.intent in self.runtime.active.READ_ONLY
            or request.intent in self.runtime.gmail_live.READ_ONLY
        )
        return request
    def _apply_context(self, request: NaturalActionRequest) -> None:
        if request.intent.startswith("mail_"):
            self._apply_mail_context(request)
        elif request.intent == "calendar_create":
            self._apply_calendar_context(request)
    def _apply_mail_context(self, request: NaturalActionRequest) -> None:
        slots = request.slots
        reference = clean_reference(slots.get("recipient_ref"))
        folded = fold_text(reference)
        pronouns = {
            "mu", "jej", "im", "jemu", "do niego", "do niej", "do nich",
        }
        last = self.runtime.last_mail()
        contextual_reference = (
            not reference
            or folded in pronouns
            or any(phrase in fold_text(request.command) for phrase in (
                "tej samej osoby", "do tej samej osoby", "napisz ponownie",
            ))
            or any(
                folded == pronoun or folded.startswith(pronoun + " ")
                for pronoun in pronouns
            )
        )
        if contextual_reference and last:
            previous = dict(last.get("slots", {}) or {})
            for key in ("recipient_ref", "recipient_email"):
                if previous.get(key):
                    slots[key] = previous[key]
            request.used_context = True
        if valid_email(slots.get("recipient_email")):
            remembered_label = clean_reference(slots.get("recipient_ref"))
            if remembered_label and not valid_email(remembered_label):
                self.recipients.remember(
                    remembered_label,
                    str(slots["recipient_email"]),
                )
    def _apply_calendar_context(self, request: NaturalActionRequest) -> None:
        slots = request.slots
        folded = fold_text(request.command)
        same_time = any(
            phrase in folded
            for phrase in ("tej samej porze", "o tej porze", "tak samo")
        )
        if not same_time or slots.get("when"):
            return
        previous = dict(
            self.context.last_action("calendar_create").get("slots", {}) or {}
        )
        try:
            old_when = datetime.fromisoformat(str(previous.get("when", "")))
        except (TypeError, ValueError):
            return
        date_text = str(slots.get("date_only", "") or "")
        if date_text:
            try:
                target_date = datetime.fromisoformat(date_text).date()
            except ValueError:
                target_date = old_when.date()
        else:
            target_date = old_when.date()
        combined = datetime.combine(
            target_date,
            time(old_when.hour, old_when.minute),
            tzinfo=old_when.tzinfo,
        )
        slots["when"] = combined.isoformat()
        slots.pop("date_only", None)
        request.used_context = True
    def _prepare_mail(self, request: NaturalActionRequest) -> None:
        slots = request.slots
        reference = clean_reference(slots.get("recipient_ref"))
        email = clean_reference(slots.get("recipient_email"))
        if is_placeholder(reference):
            reference = ""
            slots.pop("recipient_ref", None)
        if email and not valid_email(email):
            slots.pop("recipient_email", None)
            email = ""
        if email and not reference:
            reference = email
            slots["recipient_ref"] = email
        if not email and reference:
            result = self.recipients.resolve(reference)
            if result["status"] == "RESOLVED":
                email = str(result["email"])
                slots["recipient_email"] = email
            elif result["status"] == "AMBIGUOUS":
                slots["recipient_options"] = list(result.get("options", []))
        if email and reference and not valid_email(reference):
            self.recipients.remember(reference, email)
        if slots.get("body") and not slots.get("subject"):
            slots["subject"] = self.runtime.subject(str(slots["body"]))
        request.missing = []
        if not reference:
            request.missing.append("recipient_ref")
        elif not email:
            request.missing.append("recipient_email")
        if not clean_reference(slots.get("body")):
            request.missing.append("body")
        request.clarification = self._mail_prompt(request)
        if not request.missing:
            verb = "Wysłać" if request.intent == "mail_send" else "Przygotować szkic"
            request.confirmation = (
                f"{verb} do {reference} ({email}) "
                f"z tematem „{slots['subject']}”?"
            )
    def _prepare_calendar(self, request: NaturalActionRequest) -> None:
        request.slots.pop("date_only", None)
        request.missing = [
            name for name in ("title", "when")
            if not request.slots.get(name)
        ]
        prompts = {
            "title": "Co mam wpisać do kalendarza?",
            "when": "Kiedy dokładnie ma się to odbyć?",
        }
        request.clarification = " ".join(
            prompts[name] for name in request.missing
        )
        if not request.missing:
            when = datetime.fromisoformat(str(request.slots["when"]))
            reminder = request.slots.get("reminder_minutes")
            suffix = (
                f", przypomnienie {self.runtime.minutes(int(reminder))} wcześniej"
                if reminder is not None else ""
            )
            request.confirmation = (
                f"Dodać „{request.slots['title']}” {self.runtime.when(when)}{suffix}?"
            )
    @staticmethod
    def _mail_prompt(request: NaturalActionRequest) -> str:
        slots = request.slots
        prompts: list[str] = []
        if "recipient_ref" in request.missing:
            prompts.append("Podaj imię kontaktu albo adres e-mail.")
        elif "recipient_email" in request.missing:
            options = list(slots.get("recipient_options", []) or [])
            prompts.append(
                "Który adres mam wybrać: " + ", ".join(options) + "?"
                if options
                else f"Podaj adres e-mail dla {slots.get('recipient_ref', 'odbiorcy')}."
            )
        if "body" in request.missing:
            prompts.append("Co ma zawierać wiadomość?")
        return " ".join(prompts)
