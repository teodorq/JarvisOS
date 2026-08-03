from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class AutonomousLearningStore:
    """Atomic bounded storage for autonomy learning episodes and profiles."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_episodes: int = 2000,
        max_training_runs: int = 200,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.max_episodes = min(10000, max(100, int(max_episodes)))
        self.max_training_runs = min(1000, max(20, int(max_training_runs)))
        self.path = self.paths.autodev_data / "autonomous_learning.json"
        self._store = JsonStore(
            self.path,
            lambda: {
                "version": 1,
                "updated_at": "",
                "profile": self.default_profile(),
                "episodes": {},
                "episode_order": [],
                "training_runs": {},
                "training_order": [],
            },
        )

    @staticmethod
    def default_profile() -> dict[str, Any]:
        return {
            "version": 1,
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
        value["version"] = 1
        value["learned_at"] = str(
            value.get("learned_at", "")
            or self._now()
        )
        payload["profile"] = value
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def get_profile(self) -> dict[str, Any]:
        payload = self._payload(self._store.load())
        return {
            **self.default_profile(),
            **dict(payload.get("profile", {}) or {}),
        }

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
        return {
            "episodes": len(payload["episodes"]),
            "training_runs": len(payload["training_runs"]),
            "profile_active": bool(profile.get("active", False)),
            "profile_confidence": float(profile.get("confidence", 0.0) or 0.0),
            "profile_observations": int(profile.get("observations", 0) or 0),
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

        if not isinstance(episodes, dict):
            episodes = {}
        if not isinstance(episode_order, list):
            episode_order = []
        if not isinstance(training_runs, dict):
            training_runs = {}
        if not isinstance(training_order, list):
            training_order = []

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

        for item_id in normalized_episodes:
            if item_id not in normalized_episode_order:
                normalized_episode_order.append(item_id)
        for item_id in normalized_training:
            if item_id not in normalized_training_order:
                normalized_training_order.append(item_id)

        profile = payload.get("profile", {})
        if not isinstance(profile, dict):
            profile = {}

        return {
            "version": 1,
            "updated_at": str(payload.get("updated_at", "")),
            "profile": {
                **cls.default_profile(),
                **dict(profile),
            },
            "episodes": normalized_episodes,
            "episode_order": normalized_episode_order,
            "training_runs": normalized_training,
            "training_order": normalized_training_order,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
