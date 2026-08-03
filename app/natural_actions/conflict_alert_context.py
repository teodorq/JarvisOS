from __future__ import annotations

from typing import Any

from app.natural_actions.active_resolution_analysis import ActiveIssueAnalyzer


class ConflictAlertContext:
    """Builds the exact event pair represented by a proactive conflict alert."""

    @classmethod
    def analyze(cls, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for raw in events:
            item = dict(raw)
            start = ActiveIssueAnalyzer.dt(item.get("start_at"))
            if start is None:
                continue
            end = ActiveIssueAnalyzer.dt(item.get("end_at"))
            if end is None:
                continue
            rows.append({
                "id": str(item.get("id", "")),
                "title": ActiveIssueAnalyzer.clean(item.get("title")) or "wydarzenie",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
            })
        rows.sort(key=lambda item: str(item["start_at"]))
        contexts: list[dict[str, Any]] = []
        for index, first in enumerate(rows):
            first_start = ActiveIssueAnalyzer.dt(first["start_at"])
            first_end = ActiveIssueAnalyzer.dt(first["end_at"])
            for second in rows[index + 1:]:
                second_start = ActiveIssueAnalyzer.dt(second["start_at"])
                second_end = ActiveIssueAnalyzer.dt(second["end_at"])
                if None in {first_start, first_end, second_start, second_end}:
                    continue
                if second_start >= first_end:
                    break
                if second_end <= first_start:
                    continue
                issue = ActiveIssueAnalyzer.with_fingerprint({
                    "type": "conflict",
                    "first": dict(first),
                    "second": dict(second),
                    "at": max(first_start, second_start).strftime("%H:%M"),
                })
                issue["alert_context"] = True
                contexts.append(issue)
        return contexts

    @staticmethod
    def exact_pair(context: dict[str, Any]) -> dict[str, str]:
        first = dict(context.get("first", {}) or {})
        second = dict(context.get("second", {}) or {})
        return {
            "first_id": str(first.get("id", "")),
            "first_start": str(first.get("start_at", "")),
            "first_end": str(first.get("end_at", "")),
            "second_id": str(second.get("id", "")),
            "second_start": str(second.get("start_at", "")),
            "second_end": str(second.get("end_at", "")),
        }
