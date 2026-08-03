from __future__ import annotations

from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
import unittest

from app.online_assistant.google_workspace import GoogleWorkspaceProvider


class _InsertRequest:
    def __init__(self, body: dict) -> None:
        self.body = body

    def execute(self) -> dict:
        return {
            "id": "event-1",
            "summary": self.body["summary"],
            "start": dict(self.body["start"]),
            "htmlLink": "https://calendar.google.com/event?eid=event-1",
        }


class _EventsApi:
    def __init__(self) -> None:
        self.last_body: dict | None = None

    def insert(self, *, calendarId: str, body: dict, sendUpdates: str):
        self.last_body = body
        if calendarId != "primary":
            raise AssertionError(calendarId)
        if sendUpdates != "none":
            raise AssertionError(sendUpdates)
        return _InsertRequest(body)


class _CalendarService:
    def __init__(self) -> None:
        self.api = _EventsApi()

    def events(self) -> _EventsApi:
        return self.api


class B1451CalendarLiveFixTests(unittest.TestCase):
    def test_windows_fixed_offset_is_sent_as_rfc3339_without_timezone_label(self) -> None:
        service = _CalendarService()
        with TemporaryDirectory() as directory:
            provider = GoogleWorkspaceProvider(directory)
            provider._service = lambda *_args: service
            result = provider.create_calendar_event(
                title="Trening",
                start_at=datetime(
                    2026,
                    7,
                    21,
                    18,
                    0,
                    tzinfo=timezone(timedelta(hours=2)),
                ),
                duration_minutes=60,
                reminder_minutes=20,
            )

        body = service.api.last_body
        self.assertIsNotNone(body)
        assert body is not None
        self.assertEqual(body["start"]["dateTime"], "2026-07-21T18:00:00+02:00")
        self.assertEqual(body["end"]["dateTime"], "2026-07-21T19:00:00+02:00")
        self.assertNotIn("timeZone", body["start"])
        self.assertNotIn("timeZone", body["end"])
        self.assertEqual(
            body["reminders"],
            {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": 20}],
            },
        )
        self.assertEqual(result["status"], "GOOGLE_CALENDAR_EVENT_CREATED")

    def test_google_workspace_source_remains_below_existing_limit(self) -> None:
        from pathlib import Path

        source = Path(__file__).resolve().parents[1] / "app" / "online_assistant" / "google_workspace.py"
        lines = source.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 480)
        self.assertNotIn('"timeZone": zone_name', "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
