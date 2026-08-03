from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class AutonomousLearningStore:
    """Atomic bounded storage for episodes, training and profile versions."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_episodes: int = 2000,
        max_training_runs: int = 200,
        max_profile_versions: int = 100,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.max_episodes = min(10000, max(100, int(max_episodes)))
        self.max_training_runs = min(1000, max(20, int(max_training_runs)))
        self.max_profile_versions = min(
            500,
            max(10, int(max_profile_versions)),
        )
        self.path = self.paths.autodev_data / "autonomous_learning.json"
        self._store = JsonStore(
            self.path,
            lambda: self.default_payload(),
        )

    @classmethod
    def default_payload(cls) -> dict[str, Any]:
        return {
            "version": 2,
            "updated_at": "",
            "profile": cls.default_profile(),
            "profile_versions": {},
            "profile_order": [],
            "active_profile_version_id": "",
            "training_state": cls.default_training_state(),
            "episodes": {},
            "episode_order": [],
            "training_runs": {},
            "training_order": [],
        }

    @staticmethod
    def default_profile() -> dict[str, Any]:
        return {
            "version": 1,
            "profile_version_id": "",
            "active": False,
            "learned_at": "",
            "observations": 0,
            "confidence": 0.0,
            "optimizer_weights": {
                "roi": 0.28,
                "risk": 0.22,
                "time": 0.12,
                "history": 0.18,
                "priority": 0.10,
                "confidence": 0.10,
            },
            "optimizer_constraints": {
                "min_score": 0.0,
                "max_risk": 10.0,
                "max_campaigns": 30,
                "require_positive_roi": False,
            },
            "director_policy": {
                "max_retries_per_campaign": 1,
                "max_failures": 3,
                "rollback_on_stop": True,
            },
            "calibration": {},
            "recommendations": [],
            "source_training_run_id": "",
            "deployment": {},
        }

    @staticmethod
    def default_training_state() -> dict[str, Any]:
        return {
            "auto_training_enabled": True,
            "minimum_observations": 5,
            "minimum_new_episodes": 1,
            "minimum_confidence": 0.10,
            "training_in_progress": False,
            "last_trained_episode_count": 0,
            "last_training_run_id": "",
            "last_training_at": "",
            "last_deployment_status": "",
            "last_error": "",
        }

    def save_episode(
        self,
        episode: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        value = dict(episode)
        episode_id = str(value.get("episode_id", "")).strip()
        if not episode_id:
            raise ValueError("Episode uczenia wymaga episode_id.")

        payload = self._payload(self._store.load())
        created = episode_id not in payload["episodes"]
        value["updated_at"] = self._now()
        payload["episodes"][episode_id] = value
        order = payload["episode_order"]
        if episode_id in order:
            order.remove(episode_id)
        order.append(episode_id)

        while len(order) > self.max_episodes:
            removed = order.pop(0)
            payload["episodes"].pop(removed, None)

        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(value), created

    def save_episodes(
        self,
        episodes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        created = 0
        updated = 0
        for item in episodes:
            _, was_created = self.save_episode(item)
            if was_created:
                created += 1
            else:
                updated += 1
        return {
            "created": created,
            "updated": updated,
            "total": created + updated,
        }

    def list_episodes(
        self,
        *,
        limit: int = 500,
        episode_type: str | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._payload(self._store.load())
        safe_limit = min(self.max_episodes, max(1, int(limit)))
        selected = payload["episode_order"][-safe_limit:]
        values: list[dict[str, Any]] = []

        for episode_id in reversed(selected):
            item = payload["episodes"].get(episode_id)
            if not isinstance(item, dict):
                continue
            if (
                episode_type
                and str(item.get("episode_type", "")).casefold()
                != str(episode_type).casefold()
            ):
                continue
            values.append(dict(item))

        return values

    def get_episode(
        self,
        episode_id: str,
    ) -> dict[str, Any] | None:
        payload = self._payload(self._store.load())
        item = payload["episodes"].get(str(episode_id).strip())
        return dict(item) if isinstance(item, dict) else None

    def save_profile(
        self,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        value = {
            **self.default_profile(),
            **dict(profile),
        }
        value["version"] = int(value.get("version", 1) or 1)
        value["learned_at"] = str(
            value.get("learned_at", "")
            or self._now()
        )
        payload["profile"] = value
        payload["active_profile_version_id"] = str(
            value.get("profile_version_id", "")
        )
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def get_profile(self) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        return {
            **self.default_profile(),
            **dict(payload.get("profile", {}) or {}),
        }

    def save_profile_version(
        self,
        profile: dict[str, Any],
        *,
        training_run_id: str,
        deployment_status: str = "CANDIDATE",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        version_id = f"profile-{uuid4().hex}"
        sequence = len(payload["profile_order"]) + 1
        candidate = {
            **self.default_profile(),
            **dict(profile),
        }
        candidate["active"] = False
        candidate["profile_version_id"] = version_id
        candidate["source_training_run_id"] = str(training_run_id)
        candidate["version"] = sequence
        value = {
            "version_id": version_id,
            "sequence": sequence,
            "deployment_status": str(deployment_status).upper(),
            "created_at": self._now(),
            "activated_at": "",
            "training_run_id": str(training_run_id),
            "profile": candidate,
            "deployment_decision": {},
            "metadata": dict(metadata or {}),
        }
        payload["profile_versions"][version_id] = value
        payload["profile_order"].append(version_id)

        while len(payload["profile_order"]) > self.max_profile_versions:
            removed = payload["profile_order"].pop(0)
            if removed == payload["active_profile_version_id"]:
                payload["profile_order"].insert(0, removed)
                break
            payload["profile_versions"].pop(removed, None)

        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def update_profile_version(
        self,
        version_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = self._payload(self._store.load())
        key = str(version_id).strip()
        current = payload["profile_versions"].get(key)
        if not isinstance(current, dict):
            return None
        value = {
            **dict(current),
            **dict(changes),
        }
        payload["profile_versions"][key] = value
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def get_profile_version(
        self,
        version_id: str,
    ) -> dict[str, Any] | None:
        payload = self._payload(self._store.load())
        value = payload["profile_versions"].get(str(version_id).strip())
        return dict(value) if isinstance(value, dict) else None

    def list_profile_versions(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = self._payload(self._store.load())
        safe_limit = min(self.max_profile_versions, max(1, int(limit)))
        selected = payload["profile_order"][-safe_limit:]
        return [
            dict(payload["profile_versions"][version_id])
            for version_id in reversed(selected)
            if isinstance(payload["profile_versions"].get(version_id), dict)
        ]

    def activate_profile_version(
        self,
        version_id: str,
        *,
        decision: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        key = str(version_id).strip()
        selected = payload["profile_versions"].get(key)
        if not isinstance(selected, dict):
            raise ValueError("Nie znaleziono wersji profilu.")

        previous_id = str(payload.get("active_profile_version_id", ""))
        if previous_id and previous_id != key:
            previous = payload["profile_versions"].get(previous_id)
            if isinstance(previous, dict):
                previous["deployment_status"] = "ARCHIVED"
                previous["deactivated_at"] = self._now()

        profile = {
            **self.default_profile(),
            **dict(selected.get("profile", {}) or {}),
        }
        profile["active"] = True
        profile["profile_version_id"] = key
        profile["deployment"] = {
            "approved": True,
            "status": "ACTIVE",
            "activated_at": self._now(),
            "decision": dict(decision or {}),
        }
        selected["profile"] = profile
        selected["deployment_status"] = "ACTIVE"
        selected["activated_at"] = self._now()
        selected["deployment_decision"] = dict(decision or {})
        payload["profile_versions"][key] = selected
        payload["profile"] = profile
        payload["active_profile_version_id"] = key
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(selected)

    def rollback_profile(self) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        active_id = str(payload.get("active_profile_version_id", ""))
        candidates = [
            version_id
            for version_id in reversed(payload["profile_order"])
            if version_id != active_id
            and str(
                payload["profile_versions"].get(version_id, {}).get(
                    "deployment_status",
                    "",
                )
            ).upper() in {"ARCHIVED", "ACTIVE"}
        ]
        if not candidates:
            return {
                "success": False,
                "status": "AUTONOMOUS_PROFILE_ROLLBACK_UNAVAILABLE",
                "errors": ["Brak wcześniejszej aktywnej wersji profilu."],
            }

        version_id = candidates[0]
        selected = self.activate_profile_version(
            version_id,
            decision={
                "rollback": True,
                "from_version_id": active_id,
            },
        )
        return {
            "success": True,
            "status": "AUTONOMOUS_PROFILE_ROLLED_BACK",
            "version": selected,
            "profile": self.get_profile(),
            "errors": [],
        }

    def get_training_state(self) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        return {
            **self.default_training_state(),
            **dict(payload.get("training_state", {}) or {}),
        }

    def update_training_state(
        self,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        state = {
            **self.default_training_state(),
            **dict(payload.get("training_state", {}) or {}),
            **dict(changes),
        }
        state["minimum_observations"] = max(
            1,
            int(state.get("minimum_observations", 5) or 5),
        )
        state["minimum_new_episodes"] = max(
            1,
            int(state.get("minimum_new_episodes", 1) or 1),
        )
        state["minimum_confidence"] = max(
            0.0,
            min(1.0, float(state.get("minimum_confidence", 0.10) or 0.0)),
        )
        payload["training_state"] = state
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(state)

    def save_training_run(
        self,
        training_run: dict[str, Any],
    ) -> dict[str, Any]:
        value = dict(training_run)
        run_id = str(value.get("training_run_id", "")).strip()
        if not run_id:
            raise ValueError("Przebieg uczenia wymaga training_run_id.")

        payload = self._payload(self._store.load())
        value["updated_at"] = self._now()
        payload["training_runs"][run_id] = value
        order = payload["training_order"]
        if run_id in order:
            order.remove(run_id)
        order.append(run_id)

        while len(order) > self.max_training_runs:
            removed = order.pop(0)
            payload["training_runs"].pop(removed, None)

        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(value)

    def list_training_runs(
        self,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        payload = self._payload(self._store.load())
        safe_limit = min(self.max_training_runs, max(1, int(limit)))
        selected = payload["training_order"][-safe_limit:]
        return [
            dict(payload["training_runs"][run_id])
            for run_id in reversed(selected)
            if isinstance(payload["training_runs"].get(run_id), dict)
        ]

    def summary(self) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        profile = {
            **self.default_profile(),
            **dict(payload.get("profile", {}) or {}),
        }
        state = {
            **self.default_training_state(),
            **dict(payload.get("training_state", {}) or {}),
        }
        return {
            "episodes": len(payload["episodes"]),
            "training_runs": len(payload["training_runs"]),
            "profile_versions": len(payload["profile_versions"]),
            "active_profile_version_id": str(
                payload.get("active_profile_version_id", "")
            ),
            "profile_active": bool(profile.get("active", False)),
            "profile_confidence": float(profile.get("confidence", 0.0) or 0.0),
            "profile_observations": int(profile.get("observations", 0) or 0),
            "auto_training_enabled": bool(
                state.get("auto_training_enabled", True)
            ),
            "minimum_observations": int(
                state.get("minimum_observations", 5) or 5
            ),
            "minimum_new_episodes": int(
                state.get("minimum_new_episodes", 1) or 1
            ),
            "last_training_run_id": str(
                state.get("last_training_run_id", "")
            ),
            "last_deployment_status": str(
                state.get("last_deployment_status", "")
            ),
            "updated_at": str(payload.get("updated_at", "")),
            "path": str(self.path),
        }

    @classmethod
    def _payload(
        cls,
        value: Any,
    ) -> dict[str, Any]:
        payload = dict(value) if isinstance(value, dict) else {}
        episodes = payload.get("episodes", {})
        episode_order = payload.get("episode_order", [])
        training_runs = payload.get("training_runs", {})
        training_order = payload.get("training_order", [])
        profile_versions = payload.get("profile_versions", {})
        profile_order = payload.get("profile_order", [])

        if not isinstance(episodes, dict):
            episodes = {}
        if not isinstance(episode_order, list):
            episode_order = []
        if not isinstance(training_runs, dict):
            training_runs = {}
        if not isinstance(training_order, list):
            training_order = []
        if not isinstance(profile_versions, dict):
            profile_versions = {}
        if not isinstance(profile_order, list):
            profile_order = []

        normalized_episodes = {
            str(key): dict(item)
            for key, item in episodes.items()
            if isinstance(item, dict)
        }
        normalized_training = {
            str(key): dict(item)
            for key, item in training_runs.items()
            if isinstance(item, dict)
        }
        normalized_versions = {
            str(key): dict(item)
            for key, item in profile_versions.items()
            if isinstance(item, dict)
        }
        normalized_episode_order = [
            str(item_id)
            for item_id in episode_order
            if str(item_id) in normalized_episodes
        ]
        normalized_training_order = [
            str(item_id)
            for item_id in training_order
            if str(item_id) in normalized_training
        ]
        normalized_profile_order = [
            str(item_id)
            for item_id in profile_order
            if str(item_id) in normalized_versions
        ]

        for item_id in normalized_episodes:
            if item_id not in normalized_episode_order:
                normalized_episode_order.append(item_id)
        for item_id in normalized_training:
            if item_id not in normalized_training_order:
                normalized_training_order.append(item_id)
        for item_id in normalized_versions:
            if item_id not in normalized_profile_order:
                normalized_profile_order.append(item_id)

        profile = payload.get("profile", {})
        if not isinstance(profile, dict):
            profile = {}
        training_state = payload.get("training_state", {})
        if not isinstance(training_state, dict):
            training_state = {}

        return {
            "version": 2,
            "updated_at": str(payload.get("updated_at", "")),
            "profile": {
                **cls.default_profile(),
                **dict(profile),
            },
            "profile_versions": normalized_versions,
            "profile_order": normalized_profile_order,
            "active_profile_version_id": str(
                payload.get(
                    "active_profile_version_id",
                    dict(profile).get("profile_version_id", ""),
                )
            ),
            "training_state": {
                **cls.default_training_state(),
                **dict(training_state),
            },
            "episodes": normalized_episodes,
            "episode_order": normalized_episode_order,
            "training_runs": normalized_training,
            "training_order": normalized_training_order,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
