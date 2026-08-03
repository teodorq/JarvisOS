from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any

from app.natural_actions.active_resolution import ActiveResolutionService
from app.natural_actions.basic_execution import BasicNaturalActionExecution
from app.natural_actions.business_day_intelligence import BusinessDayIntelligenceService
from app.natural_actions.gmail_live_actions import GmailLiveNaturalActions
from app.natural_actions.advanced_runtime import AdvancedNaturalActionRuntime
from app.natural_actions.context import NaturalActionContext
from app.natural_actions.daily_intelligence import DailyIntelligenceService
from app.natural_actions.models import NaturalActionRequest
from app.natural_actions.proactive_day import ProactiveDayService
from app.natural_actions.startup_conflict_notification import StartupConflictNotificationPolicy
from app.natural_actions.startup_conflict_scan import StartupConflictScanService


class NaturalActionRuntime:
    """One-execution guard and public result formatting."""

    def __init__(self, context: NaturalActionContext, online: Any) -> None:
        self.context = context
        self.online = online
        self.daily = DailyIntelligenceService(context, online)
        self.business = BusinessDayIntelligenceService(context, online, self.daily)
        self.proactive = ProactiveDayService(
            getattr(online, "project_root", None), self.daily._snapshot
        )
        self.startup_conflicts = StartupConflictScanService(
            self.daily._snapshot
        )
        self.startup_notifications = StartupConflictNotificationPolicy(getattr(online, "project_root", None))
        self.advanced = AdvancedNaturalActionRuntime(online, self)
        self.gmail_live = GmailLiveNaturalActions(context, online)
        self.basic = BasicNaturalActionExecution(online, self)
        self.active = ActiveResolutionService(
            context, online, self.daily, self.proactive, self
        )

    def execute_once(self, request: NaturalActionRequest) -> str:
        fingerprint = self.fingerprint(request)
        previous = self.context.execution_result(fingerprint)
        if previous and not request.read_only:
            repeated = {
                "active_apply_suggestion": "Ta zmiana została już wykonana. Nie wykonałem jej ponownie.",
                "active_undo_calendar": "Ta zmiana została już cofnięta. Nie wykonałem jej ponownie.",
            }
            return repeated.get(
                request.intent, "To działanie zostało już wykonane. " + previous
            )
        response = self._execute(request)
        if request.intent != "active_undo_calendar":
            self.context.remember_execution(fingerprint, response)
        return response

    def _execute(self, request: NaturalActionRequest) -> str:
        if request.intent in self.business.INTENTS:
            return self.business.execute(request)
        if request.intent in self.daily.INTENTS:
            return self.daily.execute(request)
        if request.intent in self.active.INTENTS:
            return self.active.execute(request)
        if request.intent in self.advanced.INTENTS:
            return self.advanced.execute(request)
        if request.intent in self.gmail_live.INTENTS:
            return self.gmail_live.execute(request)
        response = self.basic.execute(request)
        if response is not None:
            return response
        raise ValueError("Nie mam bezpiecznego wykonawcy dla tego celu.")

    def last_mail(self) -> dict[str, Any]:
        items = [
            self.context.last_action("mail_draft"),
            self.context.last_action("mail_send"),
            self.context.last_action("gmail_reply_draft"),
        ]
        items = [item for item in items if item]
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return items[0] if items else {}

    @staticmethod
    def fingerprint(request: NaturalActionRequest) -> str:
        raw = json.dumps(
            {"intent": request.intent, "slots": request.slots},
            ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def subject(body: str) -> str:
        clean = " ".join(body.split()).strip(" .")
        first = clean.split(".", 1)[0][:70]
        return first or "Wiadomość od JARVISA"

    @staticmethod
    def when(value: datetime) -> str:
        local = value.astimezone()
        today = datetime.now(local.tzinfo).date()
        if local.date() == today:
            day = "dzisiaj"
        elif local.date().toordinal() == today.toordinal() + 1:
            day = "jutro"
        else:
            day = local.strftime("%d.%m.%Y")
        return f"{day} o {local:%H:%M}"

    @staticmethod
    def minutes(value: int) -> str:
        if value % 1440 == 0:
            return f"{value // 1440} dni"
        if value % 60 == 0:
            return f"{value // 60} godz."
        return f"{value} min"
