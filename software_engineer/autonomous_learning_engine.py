from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomous_learning_store import AutonomousLearningStore
from .autonomy_history_collector import AutonomyHistoryCollector
from .autonomy_outcome_analyzer import AutonomyOutcomeAnalyzer
from .autonomy_policy_learner import AutonomyPolicyLearner


class AutonomousLearningEngine:
    """Learns from autonomous execution history without modifying source code."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        collector: AutonomyHistoryCollector | Any | None = None,
        analyzer: AutonomyOutcomeAnalyzer | Any | None = None,
        learner: AutonomyPolicyLearner | Any | None = None,
        store: AutonomousLearningStore | Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.store = store or AutonomousLearningStore(self.project_root)
        self.collector = collector or AutonomyHistoryCollector(self.project_root)
        self.analyzer = analyzer or AutonomyOutcomeAnalyzer()
        self.learner = learner or AutonomyPolicyLearner()

    def learn(
        self,
        *,
        limit: int = 500,
        apply: bool = False,
    ) -> dict[str, Any]:
        training_run_id = f"learning-{uuid4().hex}"
        started_at = self._now()
        collected = self.collector.collect(limit=limit)
        episodes = list(collected.get("episodes", []))
        persistence = self.store.save_episodes(episodes)
        stored_episodes = self.store.list_episodes(
            limit=max(limit, len(episodes), 1)
        )
        analysis = self.analyzer.analyze(stored_episodes)
        learned = self.learner.propose(
            analysis,
            current_profile=self.store.get_profile(),
            apply_requested=bool(apply),
        )
        profile = dict(learned.get("profile", {}))
        profile["source_training_run_id"] = training_run_id

        if learned.get("applied") is True:
            profile = self.store.save_profile(profile)

        training_run = {
            "training_run_id": training_run_id,
            "status": str(learned.get("status", "UNKNOWN")),
            "success": bool(learned.get("success", False)),
            "apply_requested": bool(apply),
            "applied": bool(learned.get("applied", False)),
            "started_at": started_at,
            "completed_at": self._now(),
            "collection": {
                "episodes_count": int(
                    collected.get("episodes_count", 0) or 0
                ),
                "source_counts": dict(
                    collected.get("source_counts", {}) or {}
                ),
                "persistence": dict(persistence),
            },
            "analysis": dict(analysis),
            "profile": dict(profile),
            "errors": [],
        }
        self.store.save_training_run(training_run)

        return {
            "success": True,
            "status": str(learned.get("status", "UNKNOWN")),
            "operation": "autonomous_learning",
            "training_run_id": training_run_id,
            "applied": bool(learned.get("applied", False)),
            "enough_data": bool(learned.get("enough_data", False)),
            "minimum_observations": int(
                learned.get("minimum_observations", 0) or 0
            ),
            "collection": dict(training_run["collection"]),
            "analysis": dict(analysis),
            "profile": dict(profile),
            "store": self.store.summary(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    def observe_run(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        episode = self.collector.from_full_run(run)
        if episode is None:
            return {
                "success": True,
                "status": "AUTONOMOUS_LEARNING_OBSERVATION_SKIPPED",
                "operation": "autonomous_learning",
                "reason": "RUN_NOT_TERMINAL",
                "errors": [],
            }

        stored, created = self.store.save_episode(episode)
        return {
            "success": True,
            "status": (
                "AUTONOMOUS_LEARNING_EPISODE_RECORDED"
                if created
                else "AUTONOMOUS_LEARNING_EPISODE_UPDATED"
            ),
            "operation": "autonomous_learning",
            "episode": stored,
            "created": created,
            "store": self.store.summary(),
            "errors": [],
        }

    def status(self) -> dict[str, Any]:
        history = self.store.list_training_runs(limit=1)
        profile = self.store.get_profile()
        return {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_STATUS",
            "operation": "autonomous_learning",
            "profile": profile,
            "last_training_run": history[0] if history else {},
            "store": self.store.summary(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    def profile(self) -> dict[str, Any]:
        profile = self.store.get_profile()
        return {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_PROFILE",
            "operation": "autonomous_learning",
            "profile": profile,
            "store": self.store.summary(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    def history(
        self,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        training_runs = self.store.list_training_runs(limit=limit)
        episodes = self.store.list_episodes(limit=limit)
        return {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_HISTORY",
            "operation": "autonomous_learning",
            "training_runs": training_runs,
            "episodes": episodes,
            "store": self.store.summary(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    def explain(
        self,
        *,
        signature: str = "",
        subsystem: str = "",
    ) -> dict[str, Any]:
        episodes = self.store.list_episodes(limit=2000)
        analysis = self.analyzer.analyze(episodes)
        matches: list[dict[str, Any]] = []

        for item in episodes:
            if signature and str(item.get("signature", "")) == signature:
                matches.append(item)
                continue
            if (
                subsystem
                and subsystem in list(item.get("subsystems", []))
            ):
                matches.append(item)

        focused = self.analyzer.analyze(matches) if matches else {}
        return {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_EXPLANATION",
            "operation": "autonomous_learning",
            "signature": signature,
            "subsystem": subsystem,
            "matches": len(matches),
            "focused_analysis": focused,
            "global_analysis": analysis,
            "profile": self.store.get_profile(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
