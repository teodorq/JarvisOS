"""Scheduled Azure PAPER cycle with managed-identity durable state."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import threading
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from app.core.json_store import JsonStore
from app.market_data.forex_environment import ForexDataSettings
from app.market_data.forex_gateway import ForexReadOnlyDataGateway
from app.market_data.forex_paper_runtime import ForexDemoPaperRuntime
from app.trading.forex_activity_journal import ForexPaperActivityJournal
from app.trading.forex_cloud_activity import (
    MAX_CLOUD_ACTIVITY_EVENTS,
    sanitize_forex_cloud_activity_events,
)
from app.trading.forex_runtime_summary import ForexRuntimeCycleSummary
from cloud_service.forex_status_store import (
    FOREX_STATUS_SCHEMA_VERSION,
    ForexStatusStoreError,
    forex_status_store_from_environment,
)


_STORAGE_ACCOUNT = re.compile(r"^[a-z0-9]{3,24}$")
_CONTAINER = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
_BLOB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_DIAGNOSTIC_CODE = re.compile(r"^[A-Z0-9_:.-]{1,160}$")
_CLOUD_CYCLE_ID = re.compile(r"^AZURE-[0-9]{8}T[0-9]{6}Z-[0-9A-F]{12}$")
_STATE_ROOT = PurePosixPath("data/trading")


class CloudPaperJobError(RuntimeError):
    """Raised when the scheduled PAPER job cannot preserve state safely."""


def _diagnostic_code(value: object) -> str:
    raw = str(value or "").upper()
    cleaned = re.sub(r"[^A-Z0-9_:.-]+", "_", raw).strip("_")
    return cleaned[:160] if _DIAGNOSTIC_CODE.fullmatch(cleaned[:160]) else ""


def _cloud_cycle_id(now: datetime) -> str:
    selected = now.astimezone(timezone.utc)
    return "azure-" + selected.strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:12]


def _market_closed_result(now: datetime, cycle_id: str) -> dict[str, Any]:
    """Return a no-provider, no-state-write result outside Forex hours."""

    return {
        "status": "PAPER_CYCLE_SKIPPED",
        "mode": "AUTONOMOUS_AZURE_FOREX_PAPER",
        "cycle_id": cycle_id,
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "reason": "MARKET_CLOSED",
        "runtime_decision": "MARKET_CLOSED",
        "runtime_ready_pair_count": 0,
        "runtime_blocked_pair_count": 0,
        "runtime_execution_count": 0,
        "position_count": 0,
        "activity_events": [],
        "status_snapshot_persisted": False,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


@dataclass(frozen=True, slots=True)
class PaperStateArchive:
    max_compressed_bytes: int = 32 * 1024 * 1024
    max_uncompressed_bytes: int = 96 * 1024 * 1024
    max_file_bytes: int = 16 * 1024 * 1024
    max_files: int = 512

    def extract(self, payload: bytes, project_root: Path) -> None:
        if not payload:
            return
        if len(payload) > self.max_compressed_bytes:
            raise CloudPaperJobError("cloud_paper_state: archive_too_large")
        try:
            with ZipFile(BytesIO(payload), "r") as archive:
                members = archive.infolist()
                self._validate_members(members)
                for member in members:
                    if member.is_dir():
                        continue
                    relative = PurePosixPath(member.filename)
                    target = project_root.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
        except (BadZipFile, OSError, RuntimeError) as error:
            if isinstance(error, CloudPaperJobError):
                raise
            raise CloudPaperJobError(
                "cloud_paper_state: archive_invalid"
            ) from error

    def build(self, project_root: Path) -> bytes:
        directory = project_root / "data" / "trading"
        paths = sorted(
            path for path in directory.rglob("*.json")
            if path.is_file() and not path.is_symlink()
        ) if directory.is_dir() else []
        if len(paths) > self.max_files:
            raise CloudPaperJobError("cloud_paper_state: too_many_files")
        total = 0
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in paths:
                size = path.stat().st_size
                if size > self.max_file_bytes:
                    raise CloudPaperJobError("cloud_paper_state: file_too_large")
                total += size
                if total > self.max_uncompressed_bytes:
                    raise CloudPaperJobError(
                        "cloud_paper_state: content_too_large"
                    )
                relative = path.relative_to(project_root).as_posix()
                archive.write(path, relative)
        payload = output.getvalue()
        if len(payload) > self.max_compressed_bytes:
            raise CloudPaperJobError("cloud_paper_state: archive_too_large")
        return payload

    def empty(self) -> bytes:
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED):
            pass
        return output.getvalue()

    def _validate_members(self, members: list[ZipInfo]) -> None:
        if len(members) > self.max_files:
            raise CloudPaperJobError("cloud_paper_state: too_many_files")
        names: set[str] = set()
        total = 0
        for member in members:
            relative = PurePosixPath(member.filename)
            if (
                member.flag_bits & 0x1
                or relative.is_absolute()
                or ".." in relative.parts
                or tuple(relative.parts[:2]) != tuple(_STATE_ROOT.parts)
                or (not member.is_dir() and relative.suffix.lower() != ".json")
                or member.filename in names
            ):
                raise CloudPaperJobError("cloud_paper_state: unsafe_member")
            names.add(member.filename)
            if member.file_size > self.max_file_bytes:
                raise CloudPaperJobError("cloud_paper_state: file_too_large")
            total += member.file_size
            if total > self.max_uncompressed_bytes:
                raise CloudPaperJobError("cloud_paper_state: content_too_large")


class _LeaseRenewer:
    def __init__(self, lease: Any) -> None:
        self.lease = lease
        self.stop_event = threading.Event()
        self.error: Exception | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "_LeaseRenewer":
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop_event.set()
        self.thread.join(timeout=5)

    def check(self) -> None:
        if self.error is not None:
            raise CloudPaperJobError("cloud_paper_state: lease_lost") from self.error

    def _run(self) -> None:
        while not self.stop_event.wait(20):
            try:
                self.lease.renew()
            except Exception as error:  # Azure SDK exceptions are optional here.
                self.error = error
                self.stop_event.set()


def _configured_blob() -> tuple[Any, Any]:
    account = os.getenv("JARVIS_OS_REMOTE_STORAGE_ACCOUNT", "").strip().lower()
    container = os.getenv(
        "JARVIS_OS_FOREX_CLOUD_CONTAINER",
        "forex-paper",
    ).strip().lower()
    blob_name = os.getenv(
        "JARVIS_OS_FOREX_CLOUD_STATE_BLOB",
        "state/paper-state.zip",
    ).strip()
    if not _STORAGE_ACCOUNT.fullmatch(account):
        raise CloudPaperJobError("cloud_paper_job: invalid_storage_account")
    if not _CONTAINER.fullmatch(container):
        raise CloudPaperJobError("cloud_paper_job: invalid_container")
    if not _BLOB.fullmatch(blob_name) or ".." in PurePosixPath(blob_name).parts:
        raise CloudPaperJobError("cloud_paper_job: invalid_blob_name")
    try:
        from azure.identity import ManagedIdentityCredential
        from azure.storage.blob import BlobLeaseClient, BlobServiceClient
    except ImportError as error:
        raise CloudPaperJobError("cloud_paper_job: azure_sdk_missing") from error
    credential = ManagedIdentityCredential()
    service = BlobServiceClient(
        account_url=f"https://{account}.blob.core.windows.net",
        credential=credential,
    )
    blob = service.get_blob_client(container=container, blob=blob_name)
    return blob, BlobLeaseClient


def _validate_settings() -> ForexDataSettings:
    if os.getenv("JARVIS_OS_FOREX_CLOUD_ENABLED", "").strip().lower() != "true":
        raise CloudPaperJobError("cloud_paper_job: disabled")
    settings = ForexDataSettings.from_environment()
    if (
        not settings.enabled
        or not settings.paper_autopilot_enabled
        or settings.primary_provider != "TWELVE_DATA_CLOUD"
        or not settings.readiness()["complete"]
    ):
        raise CloudPaperJobError("cloud_paper_job: configuration_incomplete")
    return settings


def _persist_result(root: Path, result: dict[str, Any]) -> list[dict[str, Any]]:
    JsonStore(
        root / "data" / "trading" / "forex_paper_last.json",
        dict,
    ).save(result)
    journal = ForexPaperActivityJournal(root)
    journal.initialize()
    journal.record(result)
    return journal.events(limit=MAX_CLOUD_ACTIVITY_EVENTS, newest=True)


def _v3_cycle_diagnostics(
    observation: object,
    simulation: object,
    activation: object,
) -> dict[str, Any]:
    """Project a small allowlisted explanation of the latest V3 decision."""

    observed = dict(observation) if isinstance(observation, dict) else {}
    plan_value = observed.get("plan")
    plan = dict(plan_value) if isinstance(plan_value, dict) else {}
    simulation_value = (
        dict(simulation) if isinstance(simulation, dict) else {}
    )
    activation_value = (
        dict(activation) if isinstance(activation, dict) else {}
    )
    execution_value = simulation_value.get("execution")
    execution = (
        dict(execution_value) if isinstance(execution_value, dict) else {}
    )
    raw_assessments = plan.get("assessments", [])
    assessments = (
        [dict(item) for item in raw_assessments if isinstance(item, dict)]
        if isinstance(raw_assessments, list) and len(raw_assessments) <= 7
        else []
    )
    reasons: Counter[str] = Counter()
    for assessment in assessments:
        raw_reasons = assessment.get("reason_codes", [])
        if not isinstance(raw_reasons, list) or len(raw_reasons) > 12:
            continue
        for raw_code in raw_reasons:
            code = str(raw_code)
            if _DIAGNOSTIC_CODE.fullmatch(code):
                reasons.update((code,))
    raw_instructions = plan.get("instructions", [])
    instruction_count = (
        len(raw_instructions)
        if isinstance(raw_instructions, list)
        and len(raw_instructions) <= 5
        and all(isinstance(item, dict) for item in raw_instructions)
        else 0
    )
    raw_executions = execution.get("executions", [])
    execution_count = (
        len(raw_executions)
        if isinstance(raw_executions, list)
        and len(raw_executions) <= 5
        and all(isinstance(item, dict) for item in raw_executions)
        else 0
    )

    def safe_code(value: object) -> str:
        selected = str(value or "")
        return selected if _DIAGNOSTIC_CODE.fullmatch(selected) else ""

    return {
        "v3_activation_status": safe_code(activation_value.get("status")),
        "v3_activation_reason": safe_code(activation_value.get("reason")),
        "v3_plan_observation_status": safe_code(observed.get("status")),
        "v3_plan_reason": safe_code(plan.get("reason")),
        "v3_decision_status": safe_code(plan.get("decision_status")),
        "v3_simulation_reason": safe_code(simulation_value.get("reason")),
        "v3_ready_pair_count": sum(
            item.get("status") == "READY" for item in assessments
        ),
        "v3_blocked_pair_count": sum(
            item.get("status") == "BLOCKED" for item in assessments
        ),
        "v3_instruction_count": instruction_count,
        "v3_execution_count": execution_count,
        "v3_reason_codes": dict(reasons.most_common(32)),
    }


def _v3_forward_diagnostics(value: object) -> dict[str, Any]:
    """Expose only bounded codes and counters from the V3 evidence report."""

    report = dict(value) if isinstance(value, dict) else {}

    def safe_code(raw: object) -> str:
        selected = str(raw or "")
        return selected if _DIAGNOSTIC_CODE.fullmatch(selected) else ""

    def safe_count(raw: object, *, maximum: int = 1_000_000) -> int:
        if isinstance(raw, bool):
            return 0
        try:
            selected = int(raw)
        except (TypeError, ValueError, OverflowError):
            return 0
        return selected if 0 <= selected <= maximum else 0

    def safe_counts(raw: object) -> dict[str, int]:
        if not isinstance(raw, dict) or len(raw) > 32:
            return {}
        selected: dict[str, int] = {}
        for key, count in list(raw.items())[:32]:
            code = safe_code(key)
            value = safe_count(count)
            if code and value > 0:
                selected[code] = value
        return selected

    return {
        "v3_forward_status": safe_code(report.get("status")),
        "v3_forward_candidate_id": safe_code(report.get("candidate_id")),
        "v3_forward_source_state_valid": (
            report.get("source_state_valid") is True
        ),
        "v3_forward_sample_complete": (
            report.get("observation_sample_complete") is True
        ),
        "v3_forward_accepted_cycle_count": safe_count(
            report.get("accepted_cycle_count")
        ),
        "v3_forward_minimum_cycle_count": safe_count(
            report.get("minimum_accepted_cycle_count")
        ),
        "v3_forward_accepted_market_day_count": safe_count(
            report.get("accepted_market_day_count")
        ),
        "v3_forward_minimum_market_day_count": safe_count(
            report.get("minimum_market_day_count")
        ),
        "v3_forward_invalid_cycle_count": safe_count(
            report.get("invalid_cycle_count")
        ),
        "v3_forward_exclusions": safe_counts(report.get("exclusions")),
        "v3_forward_invalid_issues": safe_counts(
            report.get("invalid_issues")
        ),
    }


def _public_result(
    result: dict[str, Any],
    *,
    activity_events: object = None,
) -> dict[str, Any]:
    paper = result.get("paper")
    paper = paper if isinstance(paper, dict) else {}
    account = paper.get("account")
    account = account if isinstance(account, dict) else {}
    v3 = result.get("v3_shadow_simulation")
    v3 = v3 if isinstance(v3, dict) else {}
    v3_account = v3.get("account")
    v3_account = v3_account if isinstance(v3_account, dict) else {}
    v3_positions = v3_account.get("open_positions")
    v3_positions = v3_positions if isinstance(v3_positions, list) else []
    v3_performance = v3_account.get("performance")
    v3_performance = (
        v3_performance if isinstance(v3_performance, dict) else {}
    )
    v3_plan_observation = result.get("v3_shadow_plan_observation")
    v3_activation = result.get("v3_shadow_activation")
    v3_diagnostics = _v3_cycle_diagnostics(
        v3_plan_observation,
        v3,
        v3_activation,
    )
    v3_forward_diagnostics = _v3_forward_diagnostics(
        result.get("v3_forward_evidence")
    )
    observation = result.get("observation")
    observation = observation if isinstance(observation, dict) else {}
    observation_data = observation.get("data")
    observation_data = (
        observation_data if isinstance(observation_data, dict) else {}
    )
    observation_execution = observation.get("execution")
    observation_execution = (
        observation_execution if isinstance(observation_execution, dict) else {}
    )
    opening_blocks = observation.get("opening_blocks")
    opening_blocks = opening_blocks if isinstance(opening_blocks, list) else []
    safe_opening_blocks = [
        code
        for code in (str(value) for value in opening_blocks[:12])
        if _DIAGNOSTIC_CODE.fullmatch(code)
    ]
    raw_observation_reason = str(observation_execution.get("reason", ""))
    observation_reason = (
        raw_observation_reason
        if _DIAGNOSTIC_CODE.fullmatch(raw_observation_reason)
        else ""
    )
    raw_calendar_state = str(observation_data.get("calendar_source_state", ""))
    calendar_source_state = (
        raw_calendar_state
        if _DIAGNOSTIC_CODE.fullmatch(raw_calendar_state)
        else ""
    )
    raw_nbp_state = str(observation_data.get("nbp_source_state", ""))
    nbp_source_state = (
        raw_nbp_state
        if _DIAGNOSTIC_CODE.fullmatch(raw_nbp_state)
        else ""
    )
    result_reason = _diagnostic_code(result.get("reason", ""))
    try:
        runtime = ForexRuntimeCycleSummary.project(result)
    except (TypeError, ValueError, OverflowError, RecursionError, MemoryError):
        runtime = ForexRuntimeCycleSummary.empty_snapshot()
    raw_runtime_reasons = runtime.get("reason_codes")
    raw_runtime_reasons = (
        raw_runtime_reasons if isinstance(raw_runtime_reasons, dict) else {}
    )
    runtime_reason_codes: dict[str, int] = {}
    for raw_code, raw_count in list(raw_runtime_reasons.items())[:32]:
        code = str(raw_code)
        if not _DIAGNOSTIC_CODE.fullmatch(code):
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError, OverflowError):
            continue
        if 0 < count <= 1_000_000:
            runtime_reason_codes[code] = count
    raw_runtime_decision = str(runtime.get("decision", ""))
    runtime_decision = (
        raw_runtime_decision
        if _DIAGNOSTIC_CODE.fullmatch(raw_runtime_decision)
        else ""
    )
    return {
        "schema_version": FOREX_STATUS_SCHEMA_VERSION,
        "status": str(result.get("status", "UNKNOWN")),
        "mode": str(result.get("mode", "AUTONOMOUS_AZURE_FOREX_PAPER")),
        "cycle_id": str(result.get("cycle_id", "")),
        "observed_at": str(result.get("observed_at", "")),
        "reason": result_reason,
        "observation_status": str(observation.get("status", "")),
        "observation_reason": observation_reason,
        "observation_fully_cross_checked": (
            observation.get("fully_cross_checked") is True
        ),
        "observation_positions_unchanged": (
            observation.get("positions_unchanged") is True
        ),
        "observation_opening_blocks": safe_opening_blocks,
        "calendar_source_state": calendar_source_state,
        "nbp_source_state": nbp_source_state,
        "runtime_decision": runtime_decision,
        "runtime_ready_pair_count": int(
            runtime.get("ready_pair_count", 0) or 0
        ),
        "runtime_blocked_pair_count": int(
            runtime.get("blocked_pair_count", 0) or 0
        ),
        "runtime_execution_count": int(
            runtime.get("execution_count", 0) or 0
        ),
        "runtime_reason_codes": runtime_reason_codes,
        "runtime_high_impact_event_window": (
            runtime.get("high_impact_event_window") is True
        ),
        "position_count": int(account.get("position_count", 0) or 0),
        "v3_status": str(v3.get("status", "")),
        **v3_diagnostics,
        **v3_forward_diagnostics,
        "v3_position_count": int(v3_account.get("position_count", 0) or 0),
        "v3_closed_trade_count": int(
            v3_account.get("closed_trade_count", 0) or 0
        ),
        "v3_balance_pln": str(v3_account.get("balance_pln", "0")),
        "v3_equity_pln": str(v3_account.get("equity_pln", "0")),
        "v3_unrealized_pnl_pln": str(
            v3_account.get("unrealized_pnl_pln", "0")
        ),
        "v3_realized_pnl_pln": str(
            v3_account.get("realized_pnl_pln", "0.00")
        ),
        "v3_winning_trade_count": int(
            v3_account.get("winning_trade_count", 0) or 0
        ),
        "v3_losing_trade_count": int(
            v3_account.get("losing_trade_count", 0) or 0
        ),
        "v3_breakeven_trade_count": int(
            v3_account.get("breakeven_trade_count", 0) or 0
        ),
        "v3_win_rate_pct": str(v3_account.get("win_rate_pct", "0")),
        "v3_open_positions": [
            dict(item) for item in v3_positions[:20] if isinstance(item, dict)
        ],
        "v3_performance": dict(v3_performance),
        "activity_events": sanitize_forex_cloud_activity_events(
            activity_events or []
        ),
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def _log_summary(result: object) -> dict[str, Any]:
    """Return a small, non-sensitive completion record for Azure logs."""

    value = result if isinstance(result, dict) else {}

    def count(raw: object, *, maximum: int = 1_000_000) -> int:
        if isinstance(raw, bool):
            return 0
        try:
            selected = int(raw)
        except (TypeError, ValueError, OverflowError):
            return 0
        return selected if 0 <= selected <= maximum else 0

    def exact(raw: object, allowed: frozenset[str]) -> str:
        selected = str(raw or "")
        return selected if selected in allowed else ""

    raw_events = value.get("activity_events", [])
    try:
        events = sanitize_forex_cloud_activity_events(raw_events)
    except ValueError:
        events = []
    latest = events[-1] if events and isinstance(events[-1], dict) else {}
    raw_cycle_id = str(value.get("cycle_id", "")).upper()
    cycle_id = raw_cycle_id if _CLOUD_CYCLE_ID.fullmatch(raw_cycle_id) else ""
    return {
        "schema_version": 1,
        "status": exact(
            value.get("status"),
            frozenset({
                "PAPER_CYCLE_BLOCKED",
                "PAPER_CYCLE_COMPLETED",
                "PAPER_CYCLE_SKIPPED",
            }),
        ),
        "mode": exact(
            value.get("mode"),
            frozenset({"AUTONOMOUS_AZURE_FOREX_PAPER"}),
        ),
        "cycle_id": cycle_id,
        "runtime_decision": exact(
            value.get("runtime_decision"),
            frozenset({
                "DATA_BLOCKED",
                "MARKET_CLOSED",
                "NO_ENTRY_SIGNAL",
                "PAIR_DATA_BLOCKED",
                "PAPER_EXECUTED",
            }),
        ),
        "reason": exact(
            value.get("reason"),
            frozenset({"MARKET_CLOSED"}),
        ),
        "runtime_ready_pair_count": count(
            value.get("runtime_ready_pair_count")
        ),
        "runtime_blocked_pair_count": count(
            value.get("runtime_blocked_pair_count")
        ),
        "runtime_execution_count": count(
            value.get("runtime_execution_count")
        ),
        "position_count": count(value.get("position_count"), maximum=20),
        "v3_forward_status": exact(
            value.get("v3_forward_status"),
            frozenset({
                "BLOCKED_INVALID_FORWARD_EVIDENCE",
                "BLOCKED_SOURCE_INVALID",
                "COLLECTING_FORWARD_EVIDENCE",
                "FORWARD_OBSERVATION_SAMPLE_COMPLETE",
            }),
        ),
        "v3_forward_accepted_cycle_count": count(
            value.get("v3_forward_accepted_cycle_count")
        ),
        "v3_forward_minimum_cycle_count": count(
            value.get("v3_forward_minimum_cycle_count")
        ),
        "v3_forward_accepted_market_day_count": count(
            value.get("v3_forward_accepted_market_day_count")
        ),
        "v3_forward_minimum_market_day_count": count(
            value.get("v3_forward_minimum_market_day_count")
        ),
        "activity_event_count": min(
            len(events),
            MAX_CLOUD_ACTIVITY_EVENTS,
        ),
        "latest_activity_sequence": count(latest.get("sequence")),
        "latest_activity_kind": str(latest.get("kind", "")),
        "status_snapshot_persisted": (
            value.get("status_snapshot_persisted") is True
        ),
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def run(*, now: datetime | None = None) -> dict[str, Any]:
    settings = _validate_settings()
    selected_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cycle_id = _cloud_cycle_id(selected_now)
    if not ForexReadOnlyDataGateway.market_open(selected_now):
        return _market_closed_result(selected_now, cycle_id)
    blob, lease_type = _configured_blob()
    state = PaperStateArchive()
    try:
        from azure.core.exceptions import ResourceExistsError
    except ImportError as error:
        raise CloudPaperJobError("cloud_paper_job: azure_sdk_missing") from error
    try:
        blob.upload_blob(state.empty(), overwrite=False)
    except ResourceExistsError:
        pass
    lease = lease_type(blob)
    try:
        lease.acquire(lease_duration=60)
    except Exception as error:
        raise CloudPaperJobError("cloud_paper_state: already_running") from error
    try:
        with _LeaseRenewer(lease) as renewer, TemporaryDirectory() as directory:
            root = Path(directory) / "jarvis"
            root.mkdir()
            try:
                payload = blob.download_blob(lease=lease.id).readall()
            except Exception as error:
                raise CloudPaperJobError(
                    "cloud_paper_state: download_failed"
                ) from error
            state.extract(payload, root)
            result = ForexDemoPaperRuntime(root, settings=settings).run_once(
                cycle_id=cycle_id,
                now=selected_now,
                capture_origin="AZURE_SCHEDULED",
            )
            result.setdefault("observed_at", selected_now.isoformat())
            activity_events = _persist_result(root, result)
            renewer.check()
            archive = state.build(root)
            try:
                blob.upload_blob(
                    archive,
                    overwrite=True,
                    lease=lease.id,
                )
            except Exception as error:
                raise CloudPaperJobError(
                    "cloud_paper_state: upload_failed"
                ) from error
            renewer.check()
            public_result = _public_result(
                result,
                activity_events=activity_events,
            )
            try:
                status_store = forex_status_store_from_environment()
                if status_store is not None:
                    status_store.write(public_result)
                    public_result["status_snapshot_persisted"] = True
                else:
                    public_result["status_snapshot_persisted"] = False
            except ForexStatusStoreError:
                public_result["status_snapshot_persisted"] = False
            return public_result
    finally:
        try:
            lease.release()
        except Exception:
            pass


def main() -> int:
    try:
        result = run()
    except CloudPaperJobError as error:
        print(json.dumps({
            "status": "CLOUD_PAPER_JOB_FAILED",
            "reason": str(error),
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }, ensure_ascii=False))
        return 1
    print(json.dumps(_log_summary(result), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
