"""Scheduled Azure PAPER cycle with managed-identity durable state."""

from __future__ import annotations

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
from app.market_data.forex_paper_runtime import ForexDemoPaperRuntime
from app.trading.forex_activity_journal import ForexPaperActivityJournal


_STORAGE_ACCOUNT = re.compile(r"^[a-z0-9]{3,24}$")
_CONTAINER = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$")
_BLOB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
_STATE_ROOT = PurePosixPath("data/trading")


class CloudPaperJobError(RuntimeError):
    """Raised when the scheduled PAPER job cannot preserve state safely."""


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


def _persist_result(root: Path, result: dict[str, Any]) -> None:
    JsonStore(
        root / "data" / "trading" / "forex_paper_last.json",
        dict,
    ).save(result)
    journal = ForexPaperActivityJournal(root)
    journal.initialize()
    journal.record(result)


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    paper = result.get("paper")
    paper = paper if isinstance(paper, dict) else {}
    account = paper.get("account")
    account = account if isinstance(account, dict) else {}
    return {
        "status": str(result.get("status", "UNKNOWN")),
        "mode": str(result.get("mode", "AUTONOMOUS_AZURE_FOREX_PAPER")),
        "cycle_id": str(result.get("cycle_id", "")),
        "observed_at": str(result.get("observed_at", "")),
        "reason": str(result.get("reason", "")),
        "position_count": int(account.get("position_count", 0) or 0),
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def run() -> dict[str, Any]:
    settings = _validate_settings()
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
            now = datetime.now(timezone.utc)
            cycle_id = (
                "azure-"
                + now.strftime("%Y%m%dT%H%M%SZ-")
                + uuid4().hex[:12]
            )
            result = ForexDemoPaperRuntime(root, settings=settings).run_once(
                cycle_id=cycle_id,
                now=now,
                capture_origin="AZURE_SCHEDULED",
            )
            result.setdefault("observed_at", now.isoformat())
            _persist_result(root, result)
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
            return _public_result(result)
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
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
