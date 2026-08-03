from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import threading
from typing import Any
import uuid

from app.core.project_paths import resolve_project_root

from .deployment_receipt_ledger import DeploymentReceiptLedger
from .safe_development_models import (
    SafeDevelopmentPolicy,
    SafeDevelopmentSession,
    TERMINAL_SESSION_STATES,
)


class SafeDevelopmentStore:
    """Atomic persistent store for B201-B210 sessions and previews."""

    VERSION = 1

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: SafeDevelopmentPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or SafeDevelopmentPolicy()
        self.root = self.project_root / "data" / "autodev" / "safe_development_2"
        self.registry_path = self.root / "registry.json"
        self.sessions_root = self.root / "sessions"
        self.backups_root = self.root / "backups"
        self.receipt_ledger = DeploymentReceiptLedger(self.project_root)
        self._lock = threading.RLock()

    def record_preview(self, selected: dict[str, Any]) -> dict[str, Any]:
        preview = dict(selected or {})
        with self._lock:
            data = self._load_registry()
            data["last_preview"] = preview
            data["last_preview_at"] = self._now()
            self._save_registry(data)
        return preview

    def last_preview(self) -> dict[str, Any]:
        with self._lock:
            value = self._load_registry().get("last_preview", {})
        return dict(value) if isinstance(value, dict) else {}

    def new_session(
        self,
        *,
        target: str,
        transform: str,
        title: str,
        rationale: str,
        risk_score: float,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> SafeDevelopmentSession:
        session_id = "safe-dev-" + uuid.uuid4().hex[:16]
        now = self._now()
        session_dir = self.session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=False)
        session = SafeDevelopmentSession(
            session_id=session_id,
            status="PREPARING",
            created_at=now,
            updated_at=now,
            target=str(target),
            transform=str(transform),
            title=str(title),
            rationale=str(rationale),
            risk_score=float(risk_score),
            confidence=float(confidence),
            workspace_path=str(session_dir / "workspace"),
            metadata=dict(metadata or {}),
        )
        self.save_session(session)
        return session

    def save_session(self, session: SafeDevelopmentSession) -> SafeDevelopmentSession:
        with self._lock:
            session.updated_at = self._now()
            path = self.session_path(session.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_json(path, session.to_dict())
            registry = self._load_registry()
            sessions = dict(registry.get("sessions", {}) or {})
            sessions[session.session_id] = {
                "status": session.status,
                "target": session.target,
                "title": session.title,
                "updated_at": session.updated_at,
                "fingerprint": session.fingerprint,
            }
            order = [
                item for item in list(registry.get("order", []) or [])
                if item != session.session_id
            ]
            order.insert(0, session.session_id)
            registry.update({
                "sessions": sessions,
                "order": order,
                "latest_session_id": session.session_id,
                "updated_at": session.updated_at,
            })
            self._save_registry(registry)
            self._prune_locked(registry)
        return session

    def load_session(self, session_id: str) -> SafeDevelopmentSession:
        safe_id = self._safe_session_id(session_id)
        value = self._load_json(self.session_path(safe_id))
        if not value:
            raise FileNotFoundError("Nie znaleziono przygotowanej poprawki.")
        return SafeDevelopmentSession.from_dict(value)

    def latest_session(
        self,
        *,
        statuses: set[str] | None = None,
    ) -> SafeDevelopmentSession | None:
        with self._lock:
            order = list(self._load_registry().get("order", []) or [])
        for session_id in order:
            try:
                session = self.load_session(session_id)
            except (OSError, ValueError, TypeError):
                continue
            if statuses is None or session.status in statuses:
                return session
        return None

    def latest_ready(self) -> SafeDevelopmentSession | None:
        return self.latest_session(statuses={"READY_FOR_APPROVAL"})

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_root / self._safe_session_id(session_id)

    def session_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"

    def discard(self, session_id: str) -> SafeDevelopmentSession:
        session = self.load_session(session_id)
        if session.status == "DEPLOYED":
            raise ValueError("Wdrożonej poprawki nie można odrzucić. Użyj cofnięcia.")
        session.status = "DISCARDED"
        workspace = Path(session.workspace_path)
        if self._inside_store(workspace) and workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)
        return self.save_session(session)

    def backup_dir(self, session_id: str) -> Path:
        path = self.backups_root / self._safe_session_id(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def fingerprint(*parts: object) -> str:
        joined = "\x1f".join(str(part) for part in parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def _load_registry(self) -> dict[str, Any]:
        value = self._load_json(self.registry_path)
        if value:
            return value
        return {
            "version": self.VERSION,
            "updated_at": self._now(),
            "sessions": {},
            "order": [],
            "latest_session_id": "",
            "last_preview": {},
            "last_preview_at": "",
        }

    def _save_registry(self, value: dict[str, Any]) -> None:
        value["version"] = self.VERSION
        value["updated_at"] = self._now()
        self._atomic_json(self.registry_path, value)

    def _prune_locked(self, registry: dict[str, Any]) -> None:
        order = list(registry.get("order", []) or [])
        if len(order) <= self.policy.max_sessions:
            return
        keep = order[: self.policy.max_sessions]
        remove = order[self.policy.max_sessions:]
        sessions = dict(registry.get("sessions", {}) or {})
        for session_id in remove:
            state = str(dict(sessions.get(session_id, {}) or {}).get("status", ""))
            if state not in TERMINAL_SESSION_STATES or state == "DEPLOYED":
                keep.append(session_id)
                continue
            if (
                state == "ROLLED_BACK"
                and not self._has_archived_terminal_receipt(session_id)
            ):
                keep.append(session_id)
                continue
            path = self.session_dir(session_id)
            if self._inside_store(path):
                shutil.rmtree(path, ignore_errors=True)
            sessions.pop(session_id, None)
        registry["order"] = keep
        registry["sessions"] = sessions
        self._save_registry(registry)

    def _has_archived_terminal_receipt(self, session_id: str) -> bool:
        try:
            session = self.load_session(session_id)
        except (OSError, TypeError, ValueError):
            return False
        receipt = dict(session.rollback.get("receipt", {}) or {})
        digest = str(receipt.get("receipt_digest", ""))
        if not digest:
            return False
        return bool(self.receipt_ledger.verify(digest).get("success", False))

    def _inside_store(self, path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(self.root.resolve(strict=False))
            return True
        except ValueError:
            return False

    @staticmethod
    def _safe_session_id(value: str) -> str:
        text = str(value).strip()
        if (
            not text.startswith("safe-dev-")
            or not text.replace("-", "").isalnum()
            or len(text) > 80
        ):
            raise ValueError("Nieprawidłowy identyfikator poprawki.")
        return text

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError, TypeError):
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
