from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import threading
from typing import Any
from uuid import uuid4

from app.core.project_paths import resolve_project_root

from .autonomous_work_models import (
    CAMPAIGN_ACTIVE,
    AutonomousWorkCampaign,
    AutonomousWorkPolicy,
)


class AutonomousWorkStore:
    """Durable campaign journal with a bounded cross-process worker lease."""

    VERSION = 1

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: AutonomousWorkPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or AutonomousWorkPolicy()
        self.root = self.project_root / "data/autodev/autonomous_development_3"
        self.campaigns_root = self.root / "campaigns"
        self.registry_path = self.root / "registry.json"
        self.lease_path = self.root / "worker_lease.json"
        self._lock = threading.RLock()

    def new_campaign(self, *, requested_tasks: int) -> AutonomousWorkCampaign:
        now = self._now()
        campaign = AutonomousWorkCampaign(
            campaign_id="autodev-work-" + uuid4().hex[:16],
            status="CREATED",
            created_at=now,
            updated_at=now,
            requested_tasks=self.policy.bounded_tasks(requested_tasks),
        )
        self.event(campaign, "CAMPAIGN_CREATED")
        return self.save(campaign)

    def save(self, campaign: AutonomousWorkCampaign) -> AutonomousWorkCampaign:
        with self._lock:
            campaign.updated_at = self._now()
            self._atomic_json(self._path(campaign.campaign_id), campaign.to_dict())
            registry = self._registry()
            campaigns = dict(registry.get("campaigns", {}) or {})
            campaigns[campaign.campaign_id] = {
                "status": campaign.status,
                "requested_tasks": campaign.requested_tasks,
                "prepared_tasks": campaign.prepared_tasks,
                "updated_at": campaign.updated_at,
            }
            order = [
                item for item in list(registry.get("order", []) or [])
                if item != campaign.campaign_id
            ]
            order.insert(0, campaign.campaign_id)
            registry.update({
                "campaigns": campaigns,
                "order": order,
                "latest_campaign_id": campaign.campaign_id,
            })
            self._save_registry(registry)
            self._prune(registry)
        return campaign

    def load(self, campaign_id: str) -> AutonomousWorkCampaign:
        value = self._load_json(self._path(self._safe_id(campaign_id)))
        if not value:
            raise FileNotFoundError("Nie znaleziono kampanii AutoDev 3.")
        return AutonomousWorkCampaign.from_dict(value)

    def latest(self) -> AutonomousWorkCampaign | None:
        for campaign_id in list(self._registry().get("order", []) or []):
            try:
                return self.load(campaign_id)
            except (OSError, TypeError, ValueError):
                continue
        return None

    def active(self) -> AutonomousWorkCampaign | None:
        for campaign_id in list(self._registry().get("order", []) or []):
            try:
                campaign = self.load(campaign_id)
            except (OSError, TypeError, ValueError):
                continue
            if campaign.status in CAMPAIGN_ACTIVE:
                return campaign
        return None

    def excluded_fingerprints(self, *, except_campaign_id: str = "") -> set[str]:
        """Return tasks already attempted by other durable campaigns."""
        excluded: set[str] = set()
        for campaign_id in list(self._registry().get("order", []) or []):
            if campaign_id == except_campaign_id:
                continue
            try:
                campaign = self.load(campaign_id)
            except (OSError, TypeError, ValueError):
                continue
            excluded.update(
                str(value) for value in campaign.attempted_fingerprints if value
            )
            excluded.update(
                str(item.get("task_fingerprint", ""))
                for item in campaign.items
                if str(item.get("task_fingerprint", ""))
            )
        return excluded

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        lease = self._load_json(self.lease_path)
        for campaign_id in list(self._registry().get("order", []) or []):
            try:
                campaign = self.load(campaign_id)
            except (OSError, TypeError, ValueError):
                continue
            if campaign.status not in {"RUNNING", "CANCELLING"}:
                continue
            owns_lease = str(lease.get("campaign_id", "")) == campaign_id
            live_owner = bool(
                owns_lease
                and not self._expired(str(lease.get("expires_at", "")))
                and self._process_alive(lease.get("pid"))
            )
            if live_owner:
                continue
            if owns_lease:
                self.lease_path.unlink(missing_ok=True)
            campaign.status = "RECOVERING"
            campaign.recovery_count += 1
            campaign.lease_token = ""
            campaign.lease_expires_at = ""
            self.event(campaign, "INTERRUPTED_CAMPAIGN_RECOVERED")
            self.save(campaign)
            recovered.append(campaign.campaign_id)
        return recovered

    def has_live_lease(self, campaign_id: str) -> bool:
        lease = self._load_json(self.lease_path)
        return bool(
            str(lease.get("campaign_id", "")) == str(campaign_id)
            and not self._expired(str(lease.get("expires_at", "")))
            and self._process_alive(lease.get("pid"))
        )

    def request_cancel(self, campaign: AutonomousWorkCampaign) -> None:
        campaign.stop_requested = True
        if campaign.status in {"CREATED", "RUNNING", "RECOVERING"}:
            campaign.status = "CANCELLING"
        self.event(campaign, "CANCELLATION_REQUESTED")
        self.save(campaign)

    def acquire_lease(
        self,
        campaign: AutonomousWorkCampaign,
        token: str,
    ) -> bool:
        with self._lock:
            current = self._load_json(self.lease_path)
            if current and not self._expired(str(current.get("expires_at", ""))):
                return (
                    current.get("campaign_id") == campaign.campaign_id
                    and current.get("token") == token
                )
            if current:
                self.lease_path.unlink(missing_ok=True)
            expires = datetime.now(timezone.utc) + timedelta(
                seconds=max(10, self.policy.lease_seconds)
            )
            payload = {
                "campaign_id": campaign.campaign_id,
                "token": token,
                "pid": os.getpid(),
                "expires_at": expires.isoformat(),
            }
            self.lease_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(
                    self.lease_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                )
            except FileExistsError:
                return False
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            campaign.lease_token = token
            campaign.lease_expires_at = expires.isoformat()
            self.save(campaign)
            return True

    def renew_lease(
        self,
        campaign: AutonomousWorkCampaign,
        token: str,
    ) -> bool:
        expires_at = self._refresh_lease_file(campaign.campaign_id, token)
        if not expires_at:
            return False
        campaign.lease_expires_at = expires_at
        self.save(campaign)
        return True

    def heartbeat_lease(self, campaign_id: str, token: str) -> bool:
        """Extend a worker lease without concurrently rewriting campaign state."""
        return bool(self._refresh_lease_file(campaign_id, token))

    def _refresh_lease_file(self, campaign_id: str, token: str) -> str:
        with self._lock:
            current = self._load_json(self.lease_path)
            if (
                current.get("campaign_id") != campaign_id
                or current.get("token") != token
            ):
                return ""
            expires = datetime.now(timezone.utc) + timedelta(
                seconds=max(10, self.policy.lease_seconds)
            )
            current["expires_at"] = expires.isoformat()
            self._atomic_json(self.lease_path, current)
            return expires.isoformat()

    def release_lease(
        self,
        campaign: AutonomousWorkCampaign,
        token: str,
    ) -> None:
        with self._lock:
            current = self._load_json(self.lease_path)
            if (
                current.get("campaign_id") == campaign.campaign_id
                and current.get("token") == token
            ):
                self.lease_path.unlink(missing_ok=True)
            campaign.lease_token = ""
            campaign.lease_expires_at = ""
            self.save(campaign)

    @staticmethod
    def event(
        campaign: AutonomousWorkCampaign,
        name: str,
        **metadata: Any,
    ) -> None:
        campaign.events.append({
            "event": str(name),
            "timestamp": AutonomousWorkStore._now(),
            "metadata": dict(metadata),
        })
        campaign.events = campaign.events[-300:]

    def _registry(self) -> dict[str, Any]:
        return self._load_json(self.registry_path) or {
            "version": self.VERSION,
            "campaigns": {},
            "order": [],
            "latest_campaign_id": "",
        }

    def _save_registry(self, value: dict[str, Any]) -> None:
        value["version"] = self.VERSION
        value["updated_at"] = self._now()
        self._atomic_json(self.registry_path, value)

    def _prune(self, registry: dict[str, Any]) -> None:
        order = list(registry.get("order", []) or [])
        if len(order) <= self.policy.max_campaigns:
            return
        keep = order[: self.policy.max_campaigns]
        campaigns = dict(registry.get("campaigns", {}) or {})
        for campaign_id in order[self.policy.max_campaigns:]:
            try:
                campaign = self.load(campaign_id)
            except (OSError, TypeError, ValueError):
                continue
            if campaign.status in CAMPAIGN_ACTIVE:
                keep.append(campaign_id)
                continue
            path = self._path(campaign_id).parent
            if self._inside_root(path):
                shutil.rmtree(path, ignore_errors=True)
            campaigns.pop(campaign_id, None)
        registry["order"] = keep
        registry["campaigns"] = campaigns
        self._save_registry(registry)

    def _path(self, campaign_id: str) -> Path:
        return self.campaigns_root / self._safe_id(campaign_id) / "campaign.json"

    def _inside_root(self, path: Path) -> bool:
        try:
            path.resolve(strict=False).relative_to(self.root.resolve(strict=False))
            return True
        except ValueError:
            return False

    @staticmethod
    def _safe_id(value: str) -> str:
        text = str(value).strip()
        if (
            not text.startswith("autodev-work-")
            or not text.replace("-", "").isalnum()
            or len(text) > 80
        ):
            raise ValueError("Nieprawidłowy identyfikator kampanii AutoDev.")
        return text

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
    def _expired(value: str) -> bool:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            return moment <= datetime.now(timezone.utc)
        except (TypeError, ValueError):
            return True

    @staticmethod
    def _process_alive(value: Any) -> bool:
        try:
            pid = int(value)
            if pid <= 0:
                return False
            if pid == os.getpid():
                return True
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except (OSError, TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
