from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.cloud.forex_status import project_cloud_forex_status
from app.market_data.forex_environment import ForexDataSettings
from app.trading.forex_activity import ForexPaperActivityFeed
from app.trading.forex_cloud_activity import (
    CloudForexActivityInbox,
    ForexCloudActivityError,
    sanitize_forex_cloud_activity_events,
)
from cloud_service.forex_paper_job import _public_result
from cloud_service.forex_status_store import (
    FOREX_STATUS_MAX_BYTES,
    ForexStatusStoreError,
    forex_status_view,
    sanitize_forex_status,
)
from tests.test_cloud_forex_status import sample_status
from tests.test_cloud_forex_sync import NOW


def _event(sequence: int = 1) -> dict:
    return {
        "sequence": sequence,
        "event_id": f"{sequence:024x}",
        "occurred_at": f"2026-11-03T10:{sequence:02d}:00+00:00",
        "kind": "FOREX_V3_FORWARD_PROGRESS",
        "state": "brief",
        "message": (
            "Forex V3: zweryfikowana próbka osiągnęła 5/20 cykli. "
            "To tylko informacja o postępie — nie włącza LIVE."
        ),
        "secret": "must-not-leak",
    }


class _CloudSource:
    is_configured = True

    def __init__(self, events: list[dict]) -> None:
        self.events = events

    def snapshot(self) -> dict:
        return {"status": "READY", "activity_events": list(self.events)}


def _disabled_settings() -> ForexDataSettings:
    return ForexDataSettings(
        enabled=False,
        paper_autopilot_enabled=False,
        primary_provider="MT5_DEMO",
    )


def test_cloud_activity_transport_is_strict_and_drops_extra_fields() -> None:
    event = _event()

    assert sanitize_forex_cloud_activity_events([event]) == [{
        "sequence": 1,
        "event_id": "000000000000000000000001",
        "occurred_at": "2026-11-03T10:01:00+00:00",
        "kind": "FOREX_V3_FORWARD_PROGRESS",
        "state": "brief",
        "message": event["message"],
        "progress": 0,
        "requires_confirmation": False,
        "result_type": "FOREX_PAPER_ACTIVITY",
    }]

    event["kind"] = "ARBITRARY_CLOUD_MESSAGE"
    with pytest.raises(ForexCloudActivityError, match="invalid_kind"):
        sanitize_forex_cloud_activity_events([event])


def test_cloud_activity_transport_accepts_shadow_initialized_milestone() -> None:
    event = _event()
    event["kind"] = "FOREX_V3_SHADOW_INITIALIZED"
    event["state"] = "important"

    sanitized = sanitize_forex_cloud_activity_events([event])

    assert sanitized[0]["kind"] == "FOREX_V3_SHADOW_INITIALIZED"
    assert sanitized[0]["state"] == "important"


def test_private_status_preserves_only_valid_activity_events() -> None:
    value = sample_status()
    value["activity_events"] = [_event()]

    sanitized = sanitize_forex_status(value)
    view = forex_status_view(sanitized, now=NOW)
    projected = project_cloud_forex_status(view, now=NOW)

    assert sanitized["activity_events"][0]["event_id"].endswith("1")
    assert "secret" not in sanitized["activity_events"][0]
    assert projected["activity_events"] == sanitized["activity_events"]

    value["activity_events"][0]["state"] = "execute"
    with pytest.raises(ForexStatusStoreError, match="invalid_activity_events"):
        sanitize_forex_status(value)


def test_desktop_projection_hides_all_tampered_cloud_activity() -> None:
    payload = forex_status_view(sample_status(), now=NOW)
    payload["activity_events"] = [_event()]
    payload["activity_events"][0]["message"] = ""

    projected = project_cloud_forex_status(payload, now=NOW)

    assert projected["status"] == "STALE_DATA_BLOCKED"
    assert projected["activity_events"] == []
    assert projected["positions"] == []


def test_cloud_activity_transport_rejects_oversized_window() -> None:
    events = [_event(sequence) for sequence in range(1, 34)]

    with pytest.raises(ForexCloudActivityError, match="invalid_list"):
        sanitize_forex_cloud_activity_events(events)


def test_maximum_activity_window_fits_private_status_limit() -> None:
    value = sample_status()
    value["activity_events"] = [_event(sequence) for sequence in range(1, 33)]

    raw = json.dumps(
        sanitize_forex_status(value),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    assert len(raw) < FOREX_STATUS_MAX_BYTES


def test_public_job_result_revalidates_activity_events() -> None:
    public = _public_result({
        "status": "PAPER_CYCLE_COMPLETED",
        "cycle_id": "azure-cycle",
        "observed_at": "2026-11-03T10:01:00+00:00",
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }, activity_events=[_event()])

    assert public["activity_events"][0]["kind"] == "FOREX_V3_FORWARD_PROGRESS"
    assert "secret" not in public["activity_events"][0]
    assert public["broker_orders_sent"] is False
    assert public["live_orders_sent"] is False


def test_cloud_inbox_deduplicates_and_delivers_each_event_once() -> None:
    with TemporaryDirectory() as temporary:
        inbox = CloudForexActivityInbox(Path(temporary))

        assert inbox.sync([_event()]) == 1
        assert inbox.sync([_event()]) == 0
        delivered = inbox.poll()
        assert delivered is not None
        assert delivered["kind"] == "FOREX_V3_FORWARD_PROGRESS"
        assert inbox.poll() is None
        assert inbox.status() == {
            "event_count": 1,
            "pending_count": 0,
            "notification_count": 1,
        }
        assert inbox.history()[0]["origin"] == "AZURE_PAPER_STATUS"
        assert inbox.history()[0]["delivery_status"] == "POKAZANE"


def test_feed_delivers_cloud_event_when_local_paper_is_disabled() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        feed = ForexPaperActivityFeed(
            root,
            settings=_disabled_settings(),
            cloud_status_source=_CloudSource([_event()]),
        )

        first = feed.poll()
        assert first is not None
        assert first["activity_kind"] == "FOREX_V3_FORWARD_PROGRESS"
        assert first["history_backed"] is True
        assert feed.poll() is None
        assert feed.status()["pending_count"] == 0
        assert feed.history()[0]["origin"] == "AZURE_PAPER_STATUS"


def test_new_cloud_activity_module_remains_bounded() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "app/trading/forex_cloud_activity.py"

    assert len(path.read_text(encoding="utf-8").splitlines()) < 260
