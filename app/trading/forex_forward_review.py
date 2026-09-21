"""Immutable, read-only owner review packet for frozen Forex V2 evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from app.core.exclusive_file_lock import exclusive_file_lock
from app.core.project_paths import resolve_project_root
from app.trading.forex_candidate_v2 import ForexRegimeCandidatePolicy
from app.trading.forex_forward_evidence import (
    expected_candidate_implementation_sha256,
    verify_forex_v2_forward_evidence_report,
)
from app.trading.forex_observation import ForexObservationJournal
from app.trading.models import TradingValidationError, aware_utc


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LIMITATIONS = (
    "SIGNAL_SAMPLE_ONLY",
    "PNL_NOT_INCLUDED",
    "PROFITABILITY_NOT_VALIDATED",
    "PAPER_ACTIVATION_NOT_AUTHORIZED",
    "LIVE_TRADING_PROHIBITED",
)
_SIGNAL_COMPARISON_FIELDS = (
    "base_entry_signal_count",
    "retained_entry_signal_count",
    "filtered_entry_signal_count",
)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _content_sha256(packet: Mapping[str, Any]) -> str:
    return _canonical_sha256({
        key: value
        for key, value in packet.items()
        if key not in {"generated_at", "content_sha256"}
    })


def _safety_contract() -> dict[str, bool]:
    return {
        "performance_validated": False,
        "profitability_validated": False,
        "paper_activation_ready": False,
        "paper_activation_authorized": False,
        "live_activation_ready": False,
        "live_activation_authorized": False,
        "automatic_paper_promotion": False,
        "automatic_live_promotion": False,
        "paper_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def _signal_comparison_valid(value: object) -> bool:
    if not isinstance(value, Mapping) or set(value) != set(_SIGNAL_COMPARISON_FIELDS):
        return False
    counts = {field: value.get(field) for field in _SIGNAL_COMPARISON_FIELDS}
    if any(type(count) is not int or count < 0 for count in counts.values()):
        return False
    return counts["base_entry_signal_count"] == (
        counts["retained_entry_signal_count"]
        + counts["filtered_entry_signal_count"]
    )


def _base_packet(now: datetime) -> dict[str, Any]:
    policy = ForexRegimeCandidatePolicy()
    return {
        "schema_version": 1,
        "mode": "FOREX_V2_OWNER_REVIEW_READ_ONLY",
        "generated_at": now.isoformat(),
        "candidate_id": policy.candidate_id,
        "frozen_after": policy.frozen_after.isoformat(),
        "policy_fingerprint_sha256": policy.fingerprint_sha256,
        "implementation_sha256": expected_candidate_implementation_sha256(),
        "review_scope": "FORWARD_SIGNAL_BEHAVIOR_ONLY",
        "limitations": list(_LIMITATIONS),
        "owner_decision": "UNDECIDED",
        "owner_review_required": True,
        "packet_persisted": False,
        **_safety_contract(),
    }


def _blocked_packet(now: datetime, reason: str) -> dict[str, Any]:
    packet = {
        **_base_packet(now),
        "status": "BLOCKED_INVALID_FORWARD_EVIDENCE",
        "source_report_valid": False,
        "source_error": str(reason)[:160],
        "source_cutoff_sequence": 0,
        "source_head_hash": "",
        "source_report_content_sha256": "",
        "accepted_cycle_count": 0,
        "accepted_market_day_count": 0,
        "minimum_accepted_cycle_count": (
            ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
        ),
        "minimum_market_day_count": ForexObservationJournal.MINIMUM_MARKET_DAYS,
        "remaining_accepted_cycles": (
            ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
        ),
        "remaining_market_days": ForexObservationJournal.MINIMUM_MARKET_DAYS,
        "signal_comparison": {
            "base_entry_signal_count": 0,
            "retained_entry_signal_count": 0,
            "filtered_entry_signal_count": 0,
        },
        "accepted_observation_anchors": [],
        "review_snapshot_frozen": False,
    }
    packet["content_sha256"] = _content_sha256(packet)
    return packet


def build_forex_v2_owner_review_packet(
    forward_report: object,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a review-only packet; incomplete evidence can never become READY."""
    selected_now = aware_utc(
        generated_at or datetime.now(timezone.utc),
        "generated_at",
    )
    if not verify_forex_v2_forward_evidence_report(forward_report):
        return _blocked_packet(selected_now, "forward_review: source_report_invalid")
    report = dict(forward_report) if isinstance(forward_report, Mapping) else {}
    if (
        report.get("minimum_accepted_cycle_count")
        != ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
        or report.get("minimum_market_day_count")
        != ForexObservationJournal.MINIMUM_MARKET_DAYS
        or not _signal_comparison_valid(report.get("signal_comparison"))
    ):
        return _blocked_packet(selected_now, "forward_review: sample_contract_invalid")
    complete = verify_forex_v2_forward_evidence_report(
        report,
        require_complete=True,
    )
    packet = {
        **_base_packet(selected_now),
        "status": (
            "READY_FOR_OWNER_REVIEW_NOT_PERSISTED"
            if complete
            else "WAITING_FOR_FORWARD_SAMPLE"
        ),
        "source_report_valid": True,
        "source_error": "",
        "source_cutoff_sequence": int(report["source_cutoff_sequence"]),
        "source_head_hash": str(report["source_head_hash"]),
        "source_report_content_sha256": str(report["content_sha256"]),
        "accepted_cycle_count": int(report["accepted_cycle_count"]),
        "accepted_market_day_count": int(report["accepted_market_day_count"]),
        "minimum_accepted_cycle_count": int(report["minimum_accepted_cycle_count"]),
        "minimum_market_day_count": int(report["minimum_market_day_count"]),
        "remaining_accepted_cycles": int(report["remaining_accepted_cycles"]),
        "remaining_market_days": int(report["remaining_market_days"]),
        "signal_comparison": dict(report["signal_comparison"]),
        "accepted_observation_anchors": [
            {
                "sequence": item["sequence"],
                "observation_hash": item["observation_hash"],
            }
            for item in report["accepted_observations"]
        ],
        "review_snapshot_frozen": False,
    }
    packet["content_sha256"] = _content_sha256(packet)
    return packet


def verify_forex_v2_owner_review_packet(value: object) -> bool:
    """Verify the immutable READY packet before showing its milestone."""
    if not isinstance(value, Mapping):
        return False
    try:
        packet = dict(value)
        policy = ForexRegimeCandidatePolicy()
        generated_at = aware_utc(
            datetime.fromisoformat(str(packet["generated_at"]).replace("Z", "+00:00")),
            "generated_at",
        )
        content_sha256 = packet.get("content_sha256")
        cutoff = packet.get("source_cutoff_sequence")
        cycles = packet.get("accepted_cycle_count")
        days = packet.get("accepted_market_day_count")
        minimum_cycles = packet.get("minimum_accepted_cycle_count")
        minimum_days = packet.get("minimum_market_day_count")
        anchors = packet.get("accepted_observation_anchors")
        if (
            type(packet.get("schema_version")) is not int
            or packet.get("schema_version") != 1
            or packet.get("status") != "READY_FOR_OWNER_REVIEW"
            or packet.get("mode") != "FOREX_V2_OWNER_REVIEW_READ_ONLY"
            or packet.get("candidate_id") != policy.candidate_id
            or packet.get("frozen_after") != policy.frozen_after.isoformat()
            or generated_at < policy.frozen_after
            or packet.get("policy_fingerprint_sha256") != policy.fingerprint_sha256
            or packet.get("implementation_sha256")
            != expected_candidate_implementation_sha256()
            or packet.get("review_scope") != "FORWARD_SIGNAL_BEHAVIOR_ONLY"
            or packet.get("limitations") != list(_LIMITATIONS)
            or packet.get("owner_decision") != "UNDECIDED"
            or packet.get("owner_review_required") is not True
            or packet.get("packet_persisted") is not True
            or packet.get("source_report_valid") is not True
            or packet.get("source_error") != ""
            or type(cutoff) is not int
            or cutoff < 1
            or not _SHA256.fullmatch(str(packet.get("source_head_hash", "")))
            or not _SHA256.fullmatch(
                str(packet.get("source_report_content_sha256", ""))
            )
            or type(cycles) is not int
            or type(days) is not int
            or type(minimum_cycles) is not int
            or type(minimum_days) is not int
            or cutoff < cycles
            or minimum_cycles
            != ForexObservationJournal.MINIMUM_MARKET_OPEN_OBSERVATIONS
            or minimum_days != ForexObservationJournal.MINIMUM_MARKET_DAYS
            or cycles < minimum_cycles
            or days < minimum_days
            or packet.get("remaining_accepted_cycles") != 0
            or packet.get("remaining_market_days") != 0
            or not _signal_comparison_valid(packet.get("signal_comparison"))
            or not isinstance(anchors, list)
            or len(anchors) != cycles
            or any(
                not isinstance(item, Mapping)
                or set(item) != {"sequence", "observation_hash"}
                or type(item.get("sequence")) is not int
                or not 1 <= item["sequence"] <= cutoff
                or not isinstance(item.get("observation_hash"), str)
                or not _SHA256.fullmatch(item["observation_hash"])
                for item in anchors
            )
            or [item["sequence"] for item in anchors]
            != sorted({item["sequence"] for item in anchors})
            or packet.get("review_snapshot_frozen") is not True
            or any(packet.get(field) is not False for field in _safety_contract())
            or not isinstance(content_sha256, str)
            or not _SHA256.fullmatch(content_sha256)
            or content_sha256 != _content_sha256(packet)
        ):
            return False
        return True
    except (
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
        MemoryError,
        TradingValidationError,
    ):
        return False


def verify_forex_v2_owner_review_lineage(
    forward_report: object,
    packet: object,
) -> bool:
    """Require the frozen accepted observations to survive in later evidence."""
    if not verify_forex_v2_forward_evidence_report(
        forward_report,
        require_complete=True,
    ) or not verify_forex_v2_owner_review_packet(packet):
        return False
    report = dict(forward_report)
    review = dict(packet)
    if any(
        review[field] != report[field]
        for field in (
            "candidate_id",
            "policy_fingerprint_sha256",
            "implementation_sha256",
        )
    ):
        return False
    if report["source_cutoff_sequence"] < review["source_cutoff_sequence"]:
        return False
    if report["source_cutoff_sequence"] == review["source_cutoff_sequence"]:
        return bool(
            review["source_head_hash"] == report["source_head_hash"]
            and review["source_report_content_sha256"] == report["content_sha256"]
        )
    anchors = review["accepted_observation_anchors"]
    observations = report["accepted_observations"]
    return bool(
        len(observations) >= len(anchors)
        and all(
            current.get("sequence") == anchor["sequence"]
            and current.get("observation_hash") == anchor["observation_hash"]
            for anchor, current in zip(anchors, observations)
        )
    )


class ForexV2OwnerReviewPacket:
    """Persist the first complete candidate snapshot and never move its target."""

    MAX_PACKET_BYTES = 2_000_000

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = root / "data" / "trading" / "research" / "forward_v2_owner_review.json"
        self.lock_path = self.path.with_name(".forward_v2_owner_review.lock")

    def refresh(
        self,
        forward_report: object,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(
            generated_at or datetime.now(timezone.utc),
            "generated_at",
        )
        packet = build_forex_v2_owner_review_packet(
            forward_report,
            generated_at=selected_now,
        )
        if packet.get("status") != "READY_FOR_OWNER_REVIEW_NOT_PERSISTED":
            return packet
        packet["status"] = "READY_FOR_OWNER_REVIEW"
        packet["packet_persisted"] = True
        packet["review_snapshot_frozen"] = True
        packet["content_sha256"] = _content_sha256(packet)
        try:
            with exclusive_file_lock(
                self.lock_path,
                timeout_message="Forex V2 owner review packet lock timeout",
            ):
                if self.path.exists():
                    existing = self._load_existing()
                    if verify_forex_v2_owner_review_lineage(
                        forward_report,
                        existing,
                    ):
                        return existing
                    return _blocked_packet(
                        selected_now,
                        "forward_review: immutable_candidate_conflict",
                    )
                self._write_atomic(packet)
            return packet
        except (OSError, RuntimeError, TradingValidationError) as error:
            return _blocked_packet(
                selected_now,
                f"forward_review: persistence_failed: {error}",
            )

    def review(
        self,
        forward_report: object,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Read an existing frozen packet without creating or replacing a file."""
        selected_now = aware_utc(
            generated_at or datetime.now(timezone.utc),
            "generated_at",
        )
        current = build_forex_v2_owner_review_packet(
            forward_report,
            generated_at=selected_now,
        )
        if current.get("status") != "READY_FOR_OWNER_REVIEW_NOT_PERSISTED":
            return current
        if not self.path.exists():
            return current
        try:
            existing = self._load_existing()
        except (OSError, RuntimeError, TradingValidationError) as error:
            return _blocked_packet(
                selected_now,
                f"forward_review: saved_packet_invalid: {error}",
            )
        if verify_forex_v2_owner_review_lineage(forward_report, existing):
            return existing
        return _blocked_packet(
            selected_now,
            "forward_review: immutable_candidate_conflict",
        )

    def _load_existing(self) -> dict[str, Any]:
        try:
            size = self.path.stat().st_size
            if size <= 0 or size > self.MAX_PACKET_BYTES:
                raise TradingValidationError(
                    "forward_review: saved_packet_size_invalid"
                )
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except TradingValidationError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise TradingValidationError(
                "forward_review: saved_packet_source_invalid"
            ) from error
        if not verify_forex_v2_owner_review_packet(value):
            raise TradingValidationError("forward_review: saved_packet_invalid")
        return dict(value)

    def _write_atomic(self, packet: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".forward-v2-review-",
            suffix=".json",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(packet, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


__all__ = [
    "ForexV2OwnerReviewPacket",
    "build_forex_v2_owner_review_packet",
    "verify_forex_v2_owner_review_lineage",
    "verify_forex_v2_owner_review_packet",
]
