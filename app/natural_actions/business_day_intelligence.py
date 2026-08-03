from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable

from app.business.daily_metrics import DailyBusinessMetrics
from app.natural_actions.day_business_sources import EmailFinancialAnalyzer, money_text
from app.natural_actions.day_quality import IntelligentDayQuality
from app.natural_actions.models import NaturalActionRequest
from app.productivity.document_center import LocalDocumentCenter


class BusinessDayIntelligenceService:
    """One honest overview across daily work and connected business sources."""

    INTENTS = {
        "day_overview", "day_review", "day_business_summary", "documents_recent",
        "calendar_today_overview", "calendar_week_overview",
        "reminders_overview", "bills_overview", "advertising_overview",
        "trading_overview",
    }
    READ_ONLY = set(INTENTS)

    def __init__(self, context: Any, online: Any, daily: Any) -> None:
        self.context = context
        self.online = online
        self.daily = daily
        self.root = Path(getattr(online, "project_root", Path.cwd()))
        self.documents = LocalDocumentCenter(self.root)
        self.metrics = DailyBusinessMetrics(self.root)

    def execute(self, request: NaturalActionRequest) -> str:
        intent = request.intent
        if intent == "trading_overview":
            return self._trading(self.metrics.snapshot()["trading"])
        if intent == "documents_recent":
            return self._documents_response(self._collect("documents"))
        if intent == "calendar_today_overview":
            return self._calendar_response(self._collect("calendar"))
        if intent == "calendar_week_overview":
            return self._calendar_week_response(self._collect("calendar_week"))
        if intent == "reminders_overview":
            return self._reminders_response(self._collect("reminders"))
        if intent == "bills_overview":
            snapshot = self._collect("bills")
            self._write_bill_report(snapshot)
            return self._bills(snapshot, detailed=True)
        if intent == "advertising_overview":
            return self._advertising(self._collect("advertising"), detailed=True)
        snapshot = self._collect("day")
        return self._full_day(snapshot, business=intent == "day_business_summary", review=intent == "day_review")

    def _collect(self, scope: str) -> dict[str, Any]:
        calls: dict[str, Callable[[], Any]] = {}
        if scope in {"day"}:
            calls.update({
                "events": self._today_events,
                "mail": lambda: self._mail("day"),
                "drive_documents": self._recent_drive,
                "local_documents": self._recent_local_documents,
            })
        elif scope == "calendar":
            calls["events"] = self._today_events
        elif scope == "calendar_week":
            calls["events"] = self._week_events
        elif scope == "documents":
            calls.update({
                "drive_documents": self._recent_drive,
                "local_documents": self._recent_local_documents,
            })
        elif scope in {"bills", "advertising"}:
            calls["mail"] = lambda: self._mail(scope)
        results: dict[str, Any] = {}
        available: dict[str, bool] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(calls))) as pool:
            pending = {pool.submit(call): name for name, call in calls.items()}
            for future in as_completed(pending):
                name = pending[future]
                try:
                    results[name] = future.result()
                    available[name] = True
                except Exception:
                    results[name] = []
                    available[name] = False
        reminders = self._safe(lambda: self.online.reminders.status(), {})
        activity = self._safe(
            lambda: self.online.gmail.daily_activity(), {}
        )
        metrics = self.metrics.snapshot()
        mail = [dict(item) for item in list(results.get("mail", []) or [])]
        insights = EmailFinancialAnalyzer.analyze(mail)
        return {
            **results,
            "available": available,
            "reminders": dict(reminders or {}),
            "mail_activity": dict(activity or {}),
            "metrics": metrics,
            "mail_insights": insights,
            "completed": self.daily._completed_for(datetime.now().astimezone().date()),
            "actions": self.daily._actions_for(datetime.now().astimezone().date()),
            "now": datetime.now().astimezone(),
        }

    def _today_events(self) -> list[dict[str, Any]]:
        calendar = self.online.calendar
        today = getattr(calendar, "today", None)
        if callable(today):
            return list(today() or [])
        now = datetime.now().astimezone()
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        return list(calendar.find_events(
            "", start_at=start, end_at=start + timedelta(days=1), max_results=20
        ) or [])

    def _week_events(self) -> list[dict[str, Any]]:
        now = datetime.now().astimezone()
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        days_to_next_monday = 7 - now.weekday()
        end = start + timedelta(days=days_to_next_monday)
        return list(self.online.calendar.find_events(
            "", start_at=start, end_at=end, max_results=50
        ) or [])

    def _mail(self, scope: str) -> list[dict[str, Any]]:
        if scope in {"bills", "advertising"}:
            provider = getattr(self.online, "provider", None)
            reader = getattr(provider, "list_gmail_messages", None)
            if callable(reader):
                query = (
                    "newer_than:45d {faktura rachunek abonament płatność invoice payment plus polkomtel}"
                    if scope == "bills" else
                    "newer_than:45d {reklama google-ads meta-ads facebook-ads tiktok-ads kampania}"
                )
                return list(reader(query=query, max_results=20) or [])
        latest = getattr(self.online.gmail, "latest", None)
        if callable(latest):
            return list(latest(12) or [])
        return list(self.online.gmail.priority(12) or [])

    def _recent_drive(self) -> list[dict[str, Any]]:
        recent = getattr(self.online.drive, "recent", None)
        return list(recent(8) or []) if callable(recent) else []

    def _recent_local_documents(self) -> list[dict[str, Any]]:
        recent = getattr(self.documents, "recent", None)
        return list(recent(8) or []) if callable(recent) else []

    def _full_day(self, data: dict[str, Any], *, business: bool, review: bool = False) -> str:
        if business:
            opening = "Podsumowanie biznesowe dnia."
        elif review:
            opening = "Tak minął Twój dzień."
        else:
            opening = "Twój dzień: oto pełny plan na dziś."
        lines = [opening]
        lines.append(self._calendar(data))
        lines.append(self._mail_summary(data))
        lines.append(self._document_summary(data))
        lines.append(self._reminder_summary(data))
        lines.append(self._bills(data))
        if business:
            lines.append(self._advertising(data))
            lines.append(self._trading(data["metrics"]["trading"]))
            sales = data["metrics"]["sales"]
            if sales["connected"]:
                lines.append("Sprzedaż: " + self._metric_result(sales, "przychód"))
            done = len(data["completed"]) + len(data["actions"])
            lines.append(
                f"Wykonane działania zapisane przez Jarvisa: {done}."
            )
        priority = self.daily._priority({
            "now": data["now"], "events": data.get("events", []),
            "mail": IntelligentDayQuality.rank_mail(data.get("mail", [])),
            "reminders": data["reminders"],
        })
        ranked_mail = IntelligentDayQuality.rank_mail(data.get("mail", []))
        leading_subject = (
            self._clean(ranked_mail[0].get("subject")) if ranked_mail else ""
        )
        if leading_subject and leading_subject.casefold() in priority.casefold():
            priority = ""
        if priority:
            lines.append(f"Najlepszy następny krok: {priority}.")
        return "\n".join(line for line in lines if line)

    def _calendar(self, data: dict[str, Any]) -> str:
        if not data["available"].get("events", False):
            return "Kalendarz: nie udało mi się teraz odczytać danych."
        events = list(data.get("events", []) or [])
        if not events:
            return "Kalendarz: nie masz dziś zaplanowanych wydarzeń."
        first = dict(events[0])
        title = self._clean(first.get("title")) or "wydarzenie"
        return f"Kalendarz: masz {IntelligentDayQuality.event_count(len(events))}; najbliższe to „{title}” {self.daily._moment(first.get('start_at'))}."

    def _mail_summary(self, data: dict[str, Any]) -> str:
        if not data["available"].get("mail", False):
            return "Poczta: nie udało mi się teraz odczytać Gmaila."
        mail = list(data.get("mail", []) or [])
        important = sum(bool(item.get("important") or item.get("unread")) for item in mail)
        ranked = IntelligentDayQuality.rank_mail(mail)
        activity = data["mail_activity"]
        sent = int(activity.get("sent_today", 0) or 0)
        pending = int(activity.get("pending_drafts", 0) or 0)
        text = (
            f"Poczta: sprawdziłem {len(mail)} ostatnich wiadomości; {important} wymaga uwagi. "
            f"Dzisiaj wysłano {sent} zatwierdzonych odpowiedzi, a {pending} szkiców czeka na decyzję."
        )
        if ranked:
            text += f" Wiadomość wymagająca uwagi: „{self._clean(ranked[0].get('subject'))}”."
        return text

    def _document_summary(self, data: dict[str, Any]) -> str:
        items = self._documents(data)
        if not items:
            return "Dokumenty: nie znalazłem jeszcze ostatnio używanych plików."
        names = ", ".join(f"„{self._clean(item.get('name'))}”" for item in items[:3])
        return f"Dokumenty: znalazłem {len(items)} ostatnich plików; najnowsze to {names}."

    def _reminder_summary(self, data: dict[str, Any]) -> str:
        reminders = data["reminders"]
        pending = int(reminders.get("pending_count", 0) or 0)
        due = int(reminders.get("due_count", 0) or 0)
        if due:
            return f"Przypomnienia: Masz {IntelligentDayQuality.reminder_count(due)}. Łącznie oczekuje {pending}."
        return f"Przypomnienia: oczekuje {pending}; nic nie jest teraz pilne."

    def _bills(self, data: dict[str, Any], *, detailed: bool = False) -> str:
        insights = data["mail_insights"]
        bills = list(insights.get("bills", []) or [])
        if not bills:
            return "Rachunki: w sprawdzonych wiadomościach nie znalazłem rachunku do podliczenia."
        text = f"Rachunki: znalazłem {len(bills)} wiadomości; suma odczytanych kwot to {money_text(insights['bill_totals'])}."
        if detailed:
            names = "; ".join(self._clean(item.get("subject")) for item in bills[:6])
            text += f" Dotyczą: {names}. Zestawienie otwieram w Notatniku."
        return text

    def _advertising(self, data: dict[str, Any], *, detailed: bool = False) -> str:
        source = data["metrics"]["advertising"]
        receipts = list(data["mail_insights"].get("advertising", []) or [])
        if source["connected"]:
            text = "Reklamy: " + self._metric_result(source, "wydatki")
        elif receipts:
            text = f"Reklamy: wykryłem {len(receipts)} potwierdzeń w Gmailu na {money_text(data['mail_insights']['advertising_totals'])}."
        else:
            text = "Reklamy: źródło kosztów nie jest jeszcze podłączone i nie znalazłem potwierdzeń w Gmailu."
        if detailed and not source["connected"]:
            text += " Po podłączeniu konta reklamowego użyję jego danych jako źródła głównego."
        return text

    def _trading(self, source: dict[str, Any]) -> str:
        if not source["connected"]:
            return "Trading: źródło nie jest jeszcze podłączone, więc nie podaję wyniku."
        return "Trading: " + self._metric_result(source, "wynik")

    def _calendar_response(self, data: dict[str, Any]) -> str:
        return self._calendar(data)

    def _calendar_week_response(self, data: dict[str, Any]) -> str:
        if not data["available"].get("events", False):
            return "Kalendarz: nie udało mi się teraz odczytać planu tygodnia."
        events = sorted(
            (dict(item) for item in list(data.get("events", []) or [])),
            key=lambda item: str(item.get("start_at", "")),
        )
        if not events:
            return "Kalendarz: do końca tego tygodnia nie masz zaplanowanych wydarzeń."
        nearest = "; ".join(
            f"„{self._clean(item.get('title')) or 'wydarzenie'}” "
            f"{self.daily._moment(item.get('start_at'))}"
            for item in events[:5]
        )
        return (
            f"Kalendarz na ten tydzień: masz "
            f"{IntelligentDayQuality.event_count(len(events))}. Najbliższe: {nearest}."
        )

    def _documents_response(self, data: dict[str, Any]) -> str:
        items = self._documents(data)
        if not items:
            return "Nie znalazłem ostatnich dokumentów lokalnych ani na Dysku Google."
        names = ", ".join(f"„{self._clean(item.get('name'))}”" for item in items[:6])
        return f"Znalazłem {len(items)} ostatnich dokumentów. Najnowsze to {names}."

    def _reminders_response(self, data: dict[str, Any]) -> str:
        status = data["reminders"]
        next_item = dict(status.get("next_reminder", {}) or {})
        text = self._clean(next_item.get("text")) or "brak"
        return f"Masz {int(status.get('pending_count', 0) or 0)} oczekujących przypomnień. Najbliższe: {text}."

    def _documents(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        combined = list(data.get("drive_documents", []) or []) + list(data.get("local_documents", []) or [])
        seen: set[str] = set()
        result = []
        for raw in combined:
            item = dict(raw)
            key = self._clean(item.get("id") or item.get("path") or item.get("name")).casefold()
            if key and key not in seen:
                seen.add(key)
                result.append(item)
        return result[:12]

    def _write_bill_report(self, data: dict[str, Any]) -> None:
        directory = self.root / "AI_PLIKI" / "finanse"
        directory.mkdir(parents=True, exist_ok=True)
        insights = data["mail_insights"]
        lines = ["RACHUNKI — ZESTAWIENIE JARVISA", self._bills(data), ""]
        for index, item in enumerate(insights.get("bills", []), 1):
            amount = money_text({item["currency"]: item["amount"]}) if item.get("amount") is not None else "kwota nieodczytana"
            lines.append(f"{index}. {item.get('subject') or '(bez tematu)'} — {amount}")
        lines.append("\nŹródło: metadane i fragmenty wiadomości Gmail; sprawdź fakturę przed płatnością.")
        (directory / "RACHUNKI_DZISIAJ.txt").write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _metric_result(source: dict[str, Any], label: str) -> str:
        totals = dict(source.get("totals", {}) or {})
        if not totals:
            return f"brak zapisanych danych na dziś ({label})."
        return f"{label} {money_text(totals)} na podstawie {source.get('record_count', 0)} zapisów."

    @staticmethod
    def _safe(call: Callable[[], Any], fallback: Any) -> Any:
        try:
            return call()
        except Exception:
            return fallback

    @staticmethod
    def _clean(value: object) -> str:
        return " ".join(str(value or "").split())[:180]


__all__ = ["BusinessDayIntelligenceService"]
