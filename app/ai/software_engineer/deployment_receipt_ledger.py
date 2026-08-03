from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterator
from uuid import uuid4

from app.core.project_paths import resolve_project_root


_LEDGER_LOCKS_GUARD = threading.Lock()
_LEDGER_LOCKS: dict[str, Any] = {}


def _shared_ledger_lock(path: Path):
    key = os.path.normcase(str(path.resolve(strict=False)))
    with _LEDGER_LOCKS_GUARD:
        return _LEDGER_LOCKS.setdefault(key, threading.RLock())


class DeploymentReceiptLedger:
    """Durable, append-only-style archive for deployment evidence."""

    VERSION = 1
    INDEX_VERSION = 4
    FORBIDDEN_KEYS = (
        "password",
        "secret",
        "token",
        "credential",
        "fingerprint",
        "workspace",
        "artifact_path",
        "backup_path",
    )
    ALLOWED_KEYS = {
        "schema_version",
        "operation",
        "outcome",
        "session_id",
        "campaign_id",
        "work_item_id",
        "target",
        "source_hash",
        "proposed_hash",
        "backup_hash",
        "completed_at",
        "validation_success",
        "test_count",
        "verified",
        "automatic_approval",
        "automatic_deployment",
        "reason_digest",
        "previous_receipt_digest",
        "receipt_digest",
    }
    REQUIRED_KEYS = ALLOWED_KEYS - {
        "reason_digest",
        "previous_receipt_digest",
    }
    SUPPORTED_RECEIPT_VERSIONS = {1, 2}
    OPERATION_OUTCOMES = {
        "DEPLOY": "DEPLOYED",
        "ROLLBACK": "ROLLED_BACK",
        "AUTOMATIC_ROLLBACK": "ROLLED_BACK",
    }

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        lock_timeout_seconds: float = 5.0,
        lock_stale_seconds: float = 30.0,
        lock_poll_seconds: float = 0.01,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.root = (
            self.project_root
            / "data"
            / "autodev"
            / "safe_development_2"
            / "receipt_ledger"
        )
        self.receipts_root = self.root / "receipts"
        self.index_path = self.root / "index.json"
        self.write_lock_path = self.root / "writer_lock.json"
        self.lock_timeout_seconds = max(0.01, float(lock_timeout_seconds))
        self.lock_stale_seconds = max(1.0, float(lock_stale_seconds))
        self.lock_poll_seconds = max(0.001, float(lock_poll_seconds))
        self._lock = _shared_ledger_lock(self.root)

    def archive(self, receipt: dict[str, Any]) -> dict[str, Any]:
        value = dict(receipt or {})
        self._validate_receipt(value)
        receipt_digest = str(value["receipt_digest"]).casefold()
        path = self.receipt_path(receipt_digest)
        with self._lock, self._write_guard():
            existing = self._load_json(path)
            if existing:
                verified = self._artifact_is_valid(existing)
                if not verified or dict(existing.get("receipt", {}) or {}) != value:
                    raise ValueError(
                        "Archiwum receipt istnieje, ale nie zgadza się z dowodem."
                    )
                self._index_receipt(value, promote=False)
                return {
                    "success": True,
                    "status": "RECEIPT_ALREADY_ARCHIVED",
                    "created": False,
                    "receipt_digest": receipt_digest,
                    "archive_digest": str(existing.get("archive_digest", "")),
                }

            inventory = self._inventory()
            proposed_receipts = dict(inventory["receipts"])
            proposed_receipts[receipt_digest] = value
            conflicts, _ = self._timeline_findings(proposed_receipts)
            if conflicts:
                raise ValueError(
                    "Receipt narusza spójność osi czasu wdrożenia: "
                    + str(conflicts[0].get("code", "TIMELINE_CONFLICT"))
                    + "."
                )
            artifact = {
                "schema_version": self.VERSION,
                "archived_at": self._now(),
                "receipt": value,
            }
            artifact["archive_digest"] = self._artifact_digest(artifact)
            self._atomic_json(path, artifact)
            persisted = self._load_json(path)
            if not self._artifact_is_valid(persisted):
                path.unlink(missing_ok=True)
                raise ValueError("Nie udało się zweryfikować archiwum receipt.")
            self._index_receipt(value, promote=True)
            return {
                "success": True,
                "status": "RECEIPT_ARCHIVED",
                "created": True,
                "receipt_digest": receipt_digest,
                "archive_digest": str(persisted.get("archive_digest", "")),
            }

    def verify(self, receipt_digest: str) -> dict[str, Any]:
        try:
            path = self.receipt_path(receipt_digest)
        except ValueError as error:
            return {
                "success": False,
                "status": "INVALID_RECEIPT_DIGEST",
                "errors": [str(error)],
            }
        artifact = self._load_json(path)
        if not artifact:
            return {
                "success": False,
                "status": "RECEIPT_NOT_ARCHIVED",
                "receipt_digest": str(receipt_digest),
                "errors": [],
            }
        success = self._artifact_is_valid(artifact)
        return {
            "success": success,
            "status": (
                "RECEIPT_ARCHIVE_VERIFIED"
                if success
                else "RECEIPT_ARCHIVE_TAMPERED"
            ),
            "receipt_digest": str(receipt_digest).casefold(),
            "archive_digest": str(artifact.get("archive_digest", "")),
            "receipt": dict(artifact.get("receipt", {}) or {}) if success else {},
            "errors": [] if success else ["Hash archiwum lub receipt jest niezgodny."],
        }

    def list_receipts(
        self,
        *,
        campaign_id: str = "",
        session_id: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self.audit(repair_index=True)
        index = self._load_json(self.index_path)
        records = dict(index.get("receipts", {}) or {})
        result: list[dict[str, Any]] = []
        for digest in list(index.get("order", []) or []):
            record = dict(records.get(digest, {}) or {})
            if not record:
                continue
            if campaign_id and record.get("campaign_id") != campaign_id:
                continue
            if session_id and record.get("session_id") != session_id:
                continue
            verification = self.verify(digest)
            result.append({
                **record,
                "verified": bool(verification.get("success", False)),
            })
            if len(result) >= max(1, min(1000, int(limit))):
                break
        return result

    def latest_receipt(self, target: str) -> dict[str, Any] | None:
        value = str(target).strip()
        candidate = Path(value)
        if (
            not value
            or value == "."
            or candidate.is_absolute()
            or ".." in candidate.parts
            or not value.isascii()
            or value != candidate.as_posix()
        ):
            raise ValueError("Nieprawidłowy target historii receipt.")
        record = next(
            (
                item
                for item in self.list_receipts(limit=1000)
                if str(item.get("target", "")) == value
            ),
            None,
        )
        if record is None:
            return None
        verification = self.verify(str(record.get("receipt_digest", "")))
        if not verification.get("success", False):
            raise ValueError("Najnowszy receipt targetu jest nieprawidłowy.")
        return dict(verification.get("receipt", {}) or {})

    def audit(self, *, repair_index: bool = False) -> dict[str, Any]:
        """Compare the public index with every independently verified artifact."""
        with self._lock, self._write_guard():
            inventory = self._inventory()
            comparison = self._compare_index(inventory)
            timeline_conflicts, timeline_warnings = self._timeline_findings(
                inventory["receipts"]
            )
            repaired = False
            missing_artifacts = list(comparison["stale_index_entries"])
            if (
                repair_index
                and comparison["repair_required"]
                and not missing_artifacts
            ):
                self._write_index(
                    inventory["records"],
                    inventory["order"],
                )
                repaired = True
                comparison = self._compare_index(inventory)
            invalid = list(inventory["invalid_artifacts"])
            success = bool(
                not invalid
                and not missing_artifacts
                and not timeline_conflicts
                and not comparison["repair_required"]
            )
            if invalid:
                status = "RECEIPT_LEDGER_TAMPERED"
            elif missing_artifacts:
                status = "RECEIPT_LEDGER_EVIDENCE_MISSING"
            elif timeline_conflicts:
                status = "RECEIPT_LEDGER_TIMELINE_CONFLICT"
            elif repaired:
                status = "RECEIPT_LEDGER_REPAIRED"
            elif comparison["repair_required"]:
                status = "RECEIPT_LEDGER_REPAIR_REQUIRED"
            else:
                status = "RECEIPT_LEDGER_CURRENT"
            return {
                "success": success,
                "status": status,
                "valid_receipts": len(inventory["records"]),
                "invalid_artifacts": invalid,
                "missing_artifacts": missing_artifacts,
                "timeline_conflicts": timeline_conflicts,
                "timeline_warnings": timeline_warnings,
                "index_repaired": repaired,
                **comparison,
            }

    def rebuild_index(self) -> dict[str, Any]:
        """Atomically reconstruct the index only from valid receipt artifacts."""
        with self._lock, self._write_guard():
            inventory = self._inventory()
            comparison = self._compare_index(inventory)
            missing_artifacts = list(comparison["stale_index_entries"])
            conflicts, warnings = self._timeline_findings(
                inventory["receipts"]
            )
            self._write_index(inventory["records"], inventory["order"])
            invalid = list(inventory["invalid_artifacts"])
            success = not invalid and not missing_artifacts and not conflicts
            if invalid:
                status = "RECEIPT_INDEX_REBUILT_WITH_INVALID_ARTIFACTS"
            elif missing_artifacts:
                status = "RECEIPT_INDEX_REBUILT_WITH_MISSING_EVIDENCE"
            elif conflicts:
                status = "RECEIPT_INDEX_REBUILT_WITH_TIMELINE_CONFLICTS"
            else:
                status = "RECEIPT_INDEX_REBUILT"
            return {
                "success": success,
                "status": status,
                "valid_receipts": len(inventory["records"]),
                "invalid_artifacts": invalid,
                "missing_artifacts": missing_artifacts,
                "timeline_conflicts": conflicts,
                "timeline_warnings": warnings,
                "index_repaired": True,
            }

    def receipt_path(self, receipt_digest: str) -> Path:
        digest = str(receipt_digest).strip().casefold()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Nieprawidłowy digest receipt.")
        return self.receipts_root / f"{digest}.json"

    def _index_receipt(
        self,
        receipt: dict[str, Any],
        *,
        promote: bool,
    ) -> None:
        del receipt, promote
        inventory = self._inventory()
        comparison = self._compare_index(inventory)
        conflicts, _ = self._timeline_findings(inventory["receipts"])
        if (
            inventory["invalid_artifacts"]
            or comparison["stale_index_entries"]
            or conflicts
        ):
            raise ValueError(
                "Receipt ledger zawiera brakujący, uszkodzony "
                "lub niespójny dowód."
            )
        self._write_index(inventory["records"], inventory["order"])

    @staticmethod
    def _index_record(receipt: dict[str, Any]) -> dict[str, Any]:
        digest = str(receipt["receipt_digest"]).casefold()
        return {
            "receipt_digest": digest,
            "session_id": str(receipt.get("session_id", "")),
            "campaign_id": str(receipt.get("campaign_id", "")),
            "work_item_id": str(receipt.get("work_item_id", "")),
            "operation": str(receipt.get("operation", "")),
            "outcome": str(receipt.get("outcome", "")),
            "target": str(receipt.get("target", "")),
            "completed_at": str(receipt.get("completed_at", "")),
            "previous_receipt_digest": str(
                receipt.get("previous_receipt_digest", "")
            ),
        }

    def _inventory(self) -> dict[str, Any]:
        records: dict[str, dict[str, Any]] = {}
        receipts: dict[str, dict[str, Any]] = {}
        order_keys: dict[str, tuple[float, float, str]] = {}
        invalid: list[dict[str, str]] = []
        if self.receipts_root.is_dir():
            for path in sorted(self.receipts_root.glob("*.json")):
                digest = path.stem.casefold()
                try:
                    expected_path = self.receipt_path(digest)
                except ValueError as error:
                    invalid.append({"file": path.name, "error": str(error)})
                    continue
                if path != expected_path:
                    invalid.append({
                        "file": path.name,
                        "error": "Nazwa archiwum nie odpowiada digestowi.",
                    })
                    continue
                artifact = self._load_json(path)
                if not self._artifact_is_valid(artifact):
                    invalid.append({
                        "file": path.name,
                        "error": "Archiwum nie przeszło kontroli integralności.",
                    })
                    continue
                receipt = dict(artifact.get("receipt", {}) or {})
                if str(receipt.get("receipt_digest", "")).casefold() != digest:
                    invalid.append({
                        "file": path.name,
                        "error": "Digest receipt nie odpowiada nazwie archiwum.",
                    })
                    continue
                completed = self._parse_datetime(
                    str(receipt.get("completed_at", ""))
                )
                archived = self._parse_datetime(
                    str(artifact.get("archived_at", ""))
                )
                records[digest] = self._index_record(receipt)
                receipts[digest] = receipt
                order_keys[digest] = (
                    completed.timestamp() if completed else 0.0,
                    archived.timestamp() if archived else 0.0,
                    digest,
                )
        order = sorted(
            records,
            key=lambda digest: order_keys[digest],
            reverse=True,
        )
        return {
            "records": records,
            "receipts": receipts,
            "order": order,
            "invalid_artifacts": invalid,
        }

    def _timeline_findings(
        self,
        receipts: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for receipt in receipts.values():
            session_id = str(receipt.get("session_id", ""))
            grouped.setdefault(session_id, []).append(dict(receipt))
        conflicts: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for session_id in sorted(grouped):
            values = sorted(
                grouped[session_id],
                key=lambda item: (
                    self._parse_datetime(
                        str(item.get("completed_at", ""))
                    )
                    or datetime.min.replace(tzinfo=timezone.utc),
                    str(item.get("receipt_digest", "")),
                ),
            )
            deploys = [
                item for item in values
                if item.get("operation") == "DEPLOY"
            ]
            rollbacks = [
                item for item in values
                if item.get("operation") in {
                    "ROLLBACK",
                    "AUTOMATIC_ROLLBACK",
                }
            ]
            targets = {
                str(item.get("target", ""))
                for item in values
                if str(item.get("target", ""))
            }
            if len(targets) > 1:
                conflicts.append({
                    "code": "SESSION_TARGET_MISMATCH",
                    "session_id": session_id,
                    "receipt_digests": [
                        str(item.get("receipt_digest", ""))
                        for item in values
                    ],
                })
            if len(deploys) > 1:
                conflicts.append({
                    "code": "DUPLICATE_DEPLOY_RECEIPT",
                    "session_id": session_id,
                    "receipt_digests": [
                        str(item.get("receipt_digest", ""))
                        for item in deploys
                    ],
                })
            if len(rollbacks) > 1:
                conflicts.append({
                    "code": "DUPLICATE_ROLLBACK_RECEIPT",
                    "session_id": session_id,
                    "receipt_digests": [
                        str(item.get("receipt_digest", ""))
                        for item in rollbacks
                    ],
                })
            if rollbacks and not deploys:
                warnings.append({
                    "code": "ORPHAN_ROLLBACK_RECEIPT",
                    "session_id": session_id,
                    "receipt_digests": [
                        str(item.get("receipt_digest", ""))
                        for item in rollbacks
                    ],
                })
                continue
            if not deploys or not rollbacks:
                continue
            deployment = deploys[0]
            deployed_at = self._parse_datetime(
                str(deployment.get("completed_at", ""))
            )
            for rollback in rollbacks:
                rolled_back_at = self._parse_datetime(
                    str(rollback.get("completed_at", ""))
                )
                if (
                    deployed_at is not None
                    and rolled_back_at is not None
                    and rolled_back_at < deployed_at
                ):
                    conflicts.append({
                        "code": "ROLLBACK_PRECEDES_DEPLOYMENT",
                        "session_id": session_id,
                        "receipt_digests": [
                            str(deployment.get("receipt_digest", "")),
                            str(rollback.get("receipt_digest", "")),
                        ],
                    })
                mismatched = [
                    key
                    for key in (
                        "target",
                        "source_hash",
                        "proposed_hash",
                        "backup_hash",
                    )
                    if rollback.get(key) != deployment.get(key)
                ]
                if mismatched:
                    conflicts.append({
                        "code": "ROLLBACK_EVIDENCE_MISMATCH",
                        "session_id": session_id,
                        "fields": mismatched,
                        "receipt_digests": [
                            str(deployment.get("receipt_digest", "")),
                            str(rollback.get("receipt_digest", "")),
                        ],
                    })
        by_target: dict[str, list[dict[str, Any]]] = {}
        for receipt in receipts.values():
            target = str(receipt.get("target", ""))
            by_target.setdefault(target, []).append(dict(receipt))
        for target in sorted(by_target):
            values = sorted(
                by_target[target],
                key=lambda item: (
                    self._parse_datetime(
                        str(item.get("completed_at", ""))
                    )
                    or datetime.min.replace(tzinfo=timezone.utc),
                    str(item.get("receipt_digest", "")),
                ),
            )
            for position, receipt in enumerate(values):
                if receipt.get("schema_version") != 2:
                    continue
                digest = str(receipt.get("receipt_digest", ""))
                previous_digest = str(
                    receipt.get("previous_receipt_digest", "")
                )
                if not previous_digest:
                    if position:
                        warnings.append({
                            "code": "RECEIPT_CHAIN_BOOTSTRAP_AFTER_HISTORY",
                            "target": target,
                            "receipt_digests": [digest],
                        })
                    continue
                previous = receipts.get(previous_digest)
                if previous is None:
                    conflicts.append({
                        "code": "PREVIOUS_RECEIPT_MISSING",
                        "target": target,
                        "receipt_digests": [previous_digest, digest],
                    })
                    continue
                if str(previous.get("target", "")) != target:
                    conflicts.append({
                        "code": "PREVIOUS_RECEIPT_TARGET_MISMATCH",
                        "target": target,
                        "receipt_digests": [previous_digest, digest],
                    })
                    continue
                previous_completed = self._parse_datetime(
                    str(previous.get("completed_at", ""))
                )
                completed = self._parse_datetime(
                    str(receipt.get("completed_at", ""))
                )
                if (
                    previous_completed is None
                    or completed is None
                    or previous_completed >= completed
                ):
                    conflicts.append({
                        "code": "NON_MONOTONIC_RECEIPT_CHAIN",
                        "target": target,
                        "receipt_digests": [previous_digest, digest],
                    })
                    continue
                expected_digest = (
                    str(values[position - 1].get("receipt_digest", ""))
                    if position
                    else ""
                )
                if previous_digest != expected_digest:
                    conflicts.append({
                        "code": "RECEIPT_CHAIN_PREDECESSOR_MISMATCH",
                        "target": target,
                        "expected_receipt_digest": expected_digest,
                        "receipt_digests": [previous_digest, digest],
                    })
        return conflicts, warnings

    def _compare_index(self, inventory: dict[str, Any]) -> dict[str, Any]:
        expected_records = dict(inventory["records"])
        expected_order = list(inventory["order"])
        index_exists = self.index_path.is_file()
        index = self._load_json(self.index_path)
        valid_structure = self._index_is_valid(index)
        raw_records = index.get("receipts", {})
        raw_order = index.get("order", [])
        actual_records = dict(raw_records) if isinstance(raw_records, dict) else {}
        actual_order = list(raw_order) if isinstance(raw_order, list) else []
        expected_digests = set(expected_records)
        actual_digests = set(actual_records)
        missing = sorted(expected_digests - actual_digests)
        stale = sorted(actual_digests - expected_digests)
        mismatched = sorted(
            digest for digest in expected_digests & actual_digests
            if dict(actual_records.get(digest, {}) or {})
            != expected_records[digest]
        )
        order_matches = actual_order == expected_order
        index_required = bool(expected_records) or index_exists
        repair_required = bool(
            index_required
            and (
                not valid_structure
                or missing
                or stale
                or mismatched
                or not order_matches
            )
        )
        return {
            "index_present": index_exists,
            "index_valid": valid_structure if index_required else True,
            "repair_required": repair_required,
            "missing_index_entries": missing,
            "stale_index_entries": stale,
            "mismatched_index_entries": mismatched,
            "order_matches_inventory": order_matches if index_required else True,
        }

    def _write_index(
        self,
        records: dict[str, dict[str, Any]],
        order: list[str],
    ) -> None:
        value: dict[str, Any] = {
            "schema_version": self.INDEX_VERSION,
            "receipts": dict(records),
            "order": list(order),
            "updated_at": self._now(),
        }
        value["index_digest"] = self._index_digest(value)
        self._atomic_json(self.index_path, value)
        if not self._index_is_valid(self._load_json(self.index_path)):
            raise ValueError("Nie udało się zweryfikować indeksu receipt ledger.")

    def _index_is_valid(self, index: dict[str, Any]) -> bool:
        value = dict(index or {})
        records = value.get("receipts")
        order = value.get("order")
        provided = str(value.get("index_digest", ""))
        if (
            value.get("schema_version") != self.INDEX_VERSION
            or not isinstance(records, dict)
            or not isinstance(order, list)
            or not provided
            or not hmac.compare_digest(provided, self._index_digest(value))
        ):
            return False
        try:
            if len(order) != len(set(order)) or set(order) != set(records):
                return False
            for digest, record in records.items():
                self.receipt_path(str(digest))
                if str(dict(record or {}).get("receipt_digest", "")) != digest:
                    return False
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def _index_digest(index: dict[str, Any]) -> str:
        payload = {
            key: value for key, value in dict(index or {}).items()
            if key != "index_digest"
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _artifact_is_valid(self, artifact: dict[str, Any]) -> bool:
        if not self._verify_artifact(artifact):
            return False
        try:
            self._validate_receipt(dict(artifact.get("receipt", {}) or {}))
        except (TypeError, ValueError):
            return False
        return True

    @contextmanager
    def _write_guard(self) -> Iterator[None]:
        token = uuid4().hex
        deadline = time.monotonic() + self.lock_timeout_seconds
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            now = datetime.now(timezone.utc)
            payload = {
                "token": token,
                "pid": os.getpid(),
                "acquired_at": now.isoformat(),
                "expires_at": (
                    now + timedelta(seconds=self.lock_stale_seconds)
                ).isoformat(),
            }
            try:
                descriptor = os.open(
                    self.write_lock_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                )
            except FileExistsError:
                if self._recover_stale_lock():
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "Receipt ledger jest zajęty przez inny proces."
                    )
                time.sleep(min(self.lock_poll_seconds, remaining))
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            break
        try:
            yield
        finally:
            self._release_write_lock(token)

    def _release_write_lock(self, token: str) -> None:
        for attempt in range(8):
            current = self._load_json(self.write_lock_path)
            if str(current.get("token", "")) != token:
                return
            try:
                self.write_lock_path.unlink(missing_ok=True)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.01 * (attempt + 1))

    def _recover_stale_lock(self) -> bool:
        current = self._load_json(self.write_lock_path)
        token = str(current.get("token", ""))
        expires_at = self._parse_datetime(str(current.get("expires_at", "")))
        stale = bool(expires_at and expires_at <= datetime.now(timezone.utc))
        if not stale and self.write_lock_path.is_file():
            try:
                age = time.time() - self.write_lock_path.stat().st_mtime
            except OSError:
                return False
            stale = age >= self.lock_stale_seconds
        if not stale:
            return False
        latest = self._load_json(self.write_lock_path)
        if str(latest.get("token", "")) != token:
            return False
        self.write_lock_path.unlink(missing_ok=True)
        return True

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _validate_receipt(self, receipt: dict[str, Any]) -> None:
        if not self._verify_receipt(receipt):
            raise ValueError("Receipt ma nieprawidłowy digest.")
        unexpected = set(receipt) - self.ALLOWED_KEYS
        if unexpected:
            raise ValueError(
                "Receipt zawiera nieznane pola: "
                + ", ".join(sorted(str(key) for key in unexpected))
                + "."
            )
        for key in receipt:
            normalized = str(key).casefold()
            if any(marker in normalized for marker in self.FORBIDDEN_KEYS):
                raise ValueError(f"Receipt zawiera niedozwolone pole: {key}.")
        target_value = str(receipt.get("target", "")).strip()
        target = Path(target_value)
        if (
            not target_value
            or target_value == "."
            or target.is_absolute()
            or ".." in target.parts
            or not target_value.isascii()
            or target_value != target.as_posix()
        ):
            raise ValueError(
                "Receipt musi wskazywać kanoniczny względny target projektu."
            )
        self._validate_receipt_semantics(receipt)
        serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
        if str(self.project_root).casefold() in serialized.casefold():
            raise ValueError("Receipt zawiera bezwzględną ścieżkę projektu.")

    def _validate_receipt_semantics(self, receipt: dict[str, Any]) -> None:
        missing = self.REQUIRED_KEYS - set(receipt)
        if missing:
            raise ValueError(
                "Receipt nie zawiera wymaganych pól: "
                + ", ".join(sorted(missing))
                + "."
            )
        schema_version = receipt.get("schema_version")
        if schema_version not in self.SUPPORTED_RECEIPT_VERSIONS:
            raise ValueError("Receipt ma nieobsługiwaną wersję schematu.")
        previous_digest = str(receipt.get("previous_receipt_digest", ""))
        if schema_version == 1 and "previous_receipt_digest" in receipt:
            raise ValueError("Receipt v1 nie może zawierać poprzedniego digestu.")
        if schema_version == 2 and "previous_receipt_digest" not in receipt:
            raise ValueError("Receipt v2 wymaga poprzedniego digestu.")
        if previous_digest and not self._is_sha256(previous_digest):
            raise ValueError("Receipt ma nieprawidłowy previous_receipt_digest.")
        operation = str(receipt.get("operation", ""))
        outcome = str(receipt.get("outcome", ""))
        if self.OPERATION_OUTCOMES.get(operation) != outcome:
            raise ValueError("Receipt ma nieprawidłową parę operacji i wyniku.")
        for key in (
            "source_hash",
            "proposed_hash",
            "backup_hash",
            "receipt_digest",
        ):
            if not self._is_sha256(str(receipt.get(key, ""))):
                raise ValueError(f"Receipt ma nieprawidłowy hash: {key}.")
        reason_digest = str(receipt.get("reason_digest", ""))
        if reason_digest and not self._is_sha256(reason_digest):
            raise ValueError("Receipt ma nieprawidłowy reason_digest.")
        session_id = str(receipt.get("session_id", ""))
        if not self._safe_identifier(session_id, prefix="safe-dev-"):
            raise ValueError("Receipt ma nieprawidłowy session_id.")
        for key, prefix in (
            ("campaign_id", "autodev-work-"),
            ("work_item_id", "work-item-"),
        ):
            identifier = str(receipt.get(key, ""))
            if identifier and not self._safe_identifier(
                identifier,
                prefix=prefix,
            ):
                raise ValueError(f"Receipt ma nieprawidłowy {key}.")
        completed_at = str(receipt.get("completed_at", ""))
        try:
            completed = datetime.fromisoformat(completed_at)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Receipt ma nieprawidłowy completed_at."
            ) from error
        if completed.tzinfo is None:
            raise ValueError("Receipt completed_at musi zawierać strefę czasową.")
        for key in (
            "validation_success",
            "verified",
            "automatic_approval",
            "automatic_deployment",
        ):
            if type(receipt.get(key)) is not bool:
                raise ValueError(f"Receipt ma nieprawidłowy typ pola {key}.")
        if receipt["verified"] is not True:
            raise ValueError("Receipt nie jest oznaczony jako zweryfikowany.")
        if (
            receipt["automatic_approval"] is not False
            or receipt["automatic_deployment"] is not False
        ):
            raise ValueError("Receipt narusza bramkę ręcznej akceptacji.")
        test_count = receipt.get("test_count")
        if (
            type(test_count) is not int
            or test_count < 0
            or test_count > 1_000_000
        ):
            raise ValueError("Receipt ma nieprawidłowy test_count.")

    @staticmethod
    def _is_sha256(value: str) -> bool:
        text = str(value).strip().casefold()
        return (
            len(text) == 64
            and all(character in "0123456789abcdef" for character in text)
        )

    @staticmethod
    def _safe_identifier(value: str, *, prefix: str) -> bool:
        text = str(value).strip()
        return bool(
            text.startswith(prefix)
            and text.isascii()
            and len(text) <= 100
            and text.replace("-", "").isalnum()
        )

    @classmethod
    def _verify_receipt(cls, receipt: dict[str, Any]) -> bool:
        provided = str(dict(receipt or {}).get("receipt_digest", ""))
        return bool(provided) and hmac.compare_digest(
            provided,
            cls._receipt_digest(receipt),
        )

    @staticmethod
    def _receipt_digest(receipt: dict[str, Any]) -> str:
        payload = {
            key: value for key, value in dict(receipt or {}).items()
            if key != "receipt_digest"
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def _verify_artifact(cls, artifact: dict[str, Any]) -> bool:
        value = dict(artifact or {})
        receipt = dict(value.get("receipt", {}) or {})
        provided = str(value.get("archive_digest", ""))
        return (
            bool(provided)
            and cls._verify_receipt(receipt)
            and hmac.compare_digest(provided, cls._artifact_digest(value))
        )

    @staticmethod
    def _artifact_digest(artifact: dict[str, Any]) -> str:
        payload = {
            key: value for key, value in dict(artifact or {}).items()
            if key != "archive_digest"
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, TypeError, ValueError):
            return {}
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
