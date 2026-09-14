from __future__ import annotations

from tools.run_forex_historical_research import (
    _report_content_sha256,
    _source_manifest,
)


def _verified() -> dict[str, object]:
    return {
        "export_id": "mt5-demo-test",
        "bar_count_per_pair": 5000,
        "datasets": [
            {
                "pair": "USD_PLN",
                "bar_count": 5000,
                "fingerprint_sha256": "b" * 64,
                "matches_manifest": True,
                "unexpected_gap_count": 0,
            },
            {
                "pair": "EUR_USD",
                "bar_count": 5000,
                "fingerprint_sha256": "a" * 64,
                "matches_manifest": True,
                "unexpected_gap_count": 0,
            },
        ],
        "all_fingerprints_match": True,
        "timestamps_aligned_across_pairs": True,
        "closed_bars_only": True,
        "research_quality_ready": True,
        "expected_interval_seconds": 900,
        "historical_pln_conversion_ready": True,
    }


def test_source_manifest_is_minimal_ordered_and_secret_free() -> None:
    manifest = _source_manifest(_verified())

    assert manifest["export_id"] == "mt5-demo-test"
    assert [item["pair"] for item in manifest["datasets"]] == [
        "EUR_USD",
        "USD_PLN",
    ]
    assert manifest["closed_bars_only"] is True
    assert manifest["research_quality_ready"] is True
    assert manifest["expected_interval_seconds"] == 900
    assert "export_path" not in manifest
    assert "credentials" not in str(manifest).lower()


def test_report_hash_ignores_creation_time_but_covers_results() -> None:
    report = {
        "created_at": "2026-09-14T10:00:00+00:00",
        "source_manifest": _source_manifest(_verified()),
        "result": {"trade_count": 10, "live_orders_sent": False},
    }
    original = _report_content_sha256(report)

    report["created_at"] = "2026-09-14T11:00:00+00:00"
    assert _report_content_sha256(report) == original
    report["result"]["trade_count"] = 11
    assert _report_content_sha256(report) != original
