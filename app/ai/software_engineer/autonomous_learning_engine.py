from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomous_learning_store import AutonomousLearningStore
from .autonomous_profile_deployer import AutonomousProfileDeployer
from .autonomous_training_scheduler import AutonomousTrainingScheduler
from .autonomy_history_collector import AutonomyHistoryCollector
from .autonomy_outcome_analyzer import AutonomyOutcomeAnalyzer
from .autonomy_policy_learner import AutonomyPolicyLearner


class AutonomousLearningEngine:
    """Learns from autonomy history and safely deploys versioned profiles."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        collector: AutonomyHistoryCollector | Any | None = None,
        analyzer: AutonomyOutcomeAnalyzer | Any | None = None,
        learner: AutonomyPolicyLearner | Any | None = None,
        store: AutonomousLearningStore | Any | None = None,
        scheduler: AutonomousTrainingScheduler | Any | None = None,
        deployer: AutonomousProfileDeployer | Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.store = store or AutonomousLearningStore(self.project_root)
        self.collector = collector or AutonomyHistoryCollector(self.project_root)
        self.analyzer = analyzer or AutonomyOutcomeAnalyzer()
        self.learner = learner or AutonomyPolicyLearner()
        self.scheduler = scheduler or AutonomousTrainingScheduler()
        self.deployer = deployer or AutonomousProfileDeployer()

    def learn(
        self,
        *,
        limit: int = 500,
        apply: bool = False,
        automatic: bool = False,
    ) -> dict[str, Any]:
        training_run_id = f"learning-{uuid4().hex}"
        started_at = self._now()
        self.store.update_training_state({
            "training_in_progress": True,
            "last_error": "",
        })

        try:
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
            candidate = dict(learned.get("profile", {}) or {})
            candidate["active"] = False
            candidate["source_training_run_id"] = training_run_id
            version = self.store.save_profile_version(
                candidate,
                training_run_id=training_run_id,
                metadata={
                    "automatic": bool(automatic),
                    "apply_requested": bool(apply),
                    "observations": int(
                        analysis.get("observations", 0) or 0
                    ),
                },
            )

            deployment = {
                "success": True,
                "status": "AUTONOMOUS_PROFILE_CANDIDATE_CREATED",
                "applied": False,
                "version": version,
                "errors": [],
            }
            if apply and bool(learned.get("enough_data", False)):
                deployment = self.deployer.deploy(
                    self.store,
                    str(version["version_id"]),
                )

            applied = bool(deployment.get("applied", False))
            profile = (
                self.store.get_profile()
                if applied
                else dict(version.get("profile", {}) or {})
            )
            status = self._training_status(
                learned_status=str(learned.get("status", "UNKNOWN")),
                deployment=deployment,
                apply=bool(apply),
                automatic=bool(automatic),
            )
            training_run = {
                "training_run_id": training_run_id,
                "status": status,
                "success": bool(deployment.get("success", True)),
                "automatic": bool(automatic),
                "apply_requested": bool(apply),
                "applied": applied,
                "profile_version_id": str(version.get("version_id", "")),
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
                "candidate_profile": dict(candidate),
                "profile": dict(profile),
                "deployment": dict(deployment),
                "errors": list(deployment.get("errors", [])),
            }
            self.store.save_training_run(training_run)
            state = self.store.update_training_state({
                "training_in_progress": False,
                "last_trained_episode_count": len(stored_episodes),
                "last_training_run_id": training_run_id,
                "last_training_at": training_run["completed_at"],
                "last_deployment_status": str(
                    deployment.get("status", "")
                ),
                "last_error": "",
            })

            return {
                "success": bool(training_run["success"]),
                "status": status,
                "operation": "autonomous_learning",
                "training_run_id": training_run_id,
                "automatic": bool(automatic),
                "applied": applied,
                "enough_data": bool(learned.get("enough_data", False)),
                "minimum_observations": int(
                    learned.get("minimum_observations", 0) or 0
                ),
                "collection": dict(training_run["collection"]),
                "analysis": dict(analysis),
                "profile": dict(profile),
                "profile_version": dict(version),
                "deployment": dict(deployment),
                "training_state": dict(state),
                "store": self.store.summary(),
                "report_path": str(self.store.path),
                "errors": list(training_run["errors"]),
            }
        except Exception as error:
            completed_at = self._now()
            message = f"{type(error).__name__}: {error}"
            state = self.store.update_training_state({
                "training_in_progress": False,
                "last_training_run_id": training_run_id,
                "last_training_at": completed_at,
                "last_deployment_status": "AUTONOMOUS_TRAINING_FAILED",
                "last_error": message,
            })
            failed = {
                "training_run_id": training_run_id,
                "status": "AUTONOMOUS_TRAINING_FAILED",
                "success": False,
                "automatic": bool(automatic),
                "apply_requested": bool(apply),
                "applied": False,
                "started_at": started_at,
                "completed_at": completed_at,
                "errors": [message],
            }
            self.store.save_training_run(failed)
            return {
                "success": False,
                "status": "AUTONOMOUS_TRAINING_FAILED",
                "operation": "autonomous_learning",
                "training_run_id": training_run_id,
                "automatic": bool(automatic),
                "applied": False,
                "training_state": state,
                "store": self.store.summary(),
                "report_path": str(self.store.path),
                "errors": [message],
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
        decision = self.scheduler.evaluate(
            summary=self.store.summary(),
            state=self.store.get_training_state(),
        )
        auto_training: dict[str, Any] = dict(decision)
        if created and bool(decision.get("ready", False)):
            auto_training = self.learn(
                limit=5000,
                apply=True,
                automatic=True,
            )
        elif not created:
            auto_training = {
                **dict(decision),
                "status": "AUTONOMOUS_TRAINING_DUPLICATE_EPISODE_SKIPPED",
                "ready": False,
            }

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
            "auto_training": auto_training,
            "store": self.store.summary(),
            "errors": [],
        }

    def reconcile_failed_runs(
        self,
        *,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Backfills terminal failed runs missed by older workflow versions."""
        full_store = getattr(self.collector, "full_store", None)
        if full_store is None or not hasattr(full_store, "list_recent"):
            return {
                "success": True,
                "status": "AUTONOMOUS_LEARNING_RECONCILIATION_UNAVAILABLE",
                "created": 0,
                "duplicates": 0,
                "skipped": 0,
                "errors": [],
            }

        safe_limit = min(500, max(1, int(limit)))
        try:
            runs = list(full_store.list_recent(limit=safe_limit))
        except Exception as error:
            return {
                "success": False,
                "status": "AUTONOMOUS_LEARNING_RECONCILIATION_FAILED",
                "created": 0,
                "duplicates": 0,
                "skipped": 0,
                "errors": [f"{type(error).__name__}: {error}"],
            }

        created = 0
        duplicates = 0
        skipped = 0
        errors: list[str] = []

        for run in reversed(runs):
            if not isinstance(run, dict):
                skipped += 1
                continue
            status = str(run.get("status", "")).upper()
            if not any(
                marker in status
                for marker in ("FAILED", "ROLLED_BACK", "CANCELLED")
            ):
                skipped += 1
                continue

            try:
                episode = self.collector.from_full_run(run)
                if episode is None:
                    skipped += 1
                    continue
                episode_id = str(episode.get("episode_id", "")).strip()
                if episode_id and self.store.get_episode(episode_id) is not None:
                    duplicates += 1
                    continue

                observation = self.observe_run(run)
                if bool(observation.get("created", False)):
                    created += 1
                else:
                    duplicates += 1

                if hasattr(full_store, "save"):
                    updated = dict(run)
                    updated["learning_observation"] = dict(observation)
                    full_store.save(updated)
            except Exception as error:
                errors.append(f"{type(error).__name__}: {error}")

        return {
            "success": not errors,
            "status": (
                "AUTONOMOUS_LEARNING_FAILED_RUNS_RECONCILED"
                if not errors
                else "AUTONOMOUS_LEARNING_RECONCILIATION_PARTIAL"
            ),
            "created": created,
            "duplicates": duplicates,
            "skipped": skipped,
            "errors": errors,
        }

    def status(self) -> dict[str, Any]:
        reconciliation = self.reconcile_failed_runs(limit=100)
        history = self.store.list_training_runs(limit=1)
        profile = self.store.get_profile()
        state = self.store.get_training_state()
        auto_training = self.scheduler.evaluate(
            summary=self.store.summary(),
            state=state,
        )
        return {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_STATUS",
            "operation": "autonomous_learning",
            "profile": profile,
            "profile_versions": self.store.list_profile_versions(limit=5),
            "last_training_run": history[0] if history else {},
            "training_state": state,
            "auto_training": auto_training,
            "reconciliation": reconciliation,
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
            "profile_versions": self.store.list_profile_versions(limit=20),
            "training_state": self.store.get_training_state(),
            "store": self.store.summary(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    def versions(
        self,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_PROFILE_VERSIONS",
            "operation": "autonomous_learning",
            "profile": self.store.get_profile(),
            "profile_versions": self.store.list_profile_versions(limit=limit),
            "training_state": self.store.get_training_state(),
            "store": self.store.summary(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    def activate_profile(
        self,
        version_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        result = self.deployer.deploy(
            self.store,
            version_id,
            force=force,
        )
        return {
            **dict(result),
            "operation": "autonomous_learning",
            "profile": self.store.get_profile(),
            "store": self.store.summary(),
            "report_path": str(self.store.path),
        }

    def rollback_profile(self) -> dict[str, Any]:
        result = self.store.rollback_profile()
        return {
            **dict(result),
            "operation": "autonomous_learning",
            "store": self.store.summary(),
            "report_path": str(self.store.path),
        }

    def configure_auto_training(
        self,
        *,
        enabled: bool | None = None,
        minimum_observations: int | None = None,
        minimum_new_episodes: int | None = None,
        minimum_confidence: float | None = None,
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if enabled is not None:
            changes["auto_training_enabled"] = bool(enabled)
        if minimum_observations is not None:
            changes["minimum_observations"] = int(minimum_observations)
        if minimum_new_episodes is not None:
            changes["minimum_new_episodes"] = int(minimum_new_episodes)
        if minimum_confidence is not None:
            changes["minimum_confidence"] = float(minimum_confidence)
        state = self.store.update_training_state(changes)
        decision = self.scheduler.evaluate(
            summary=self.store.summary(),
            state=state,
        )
        return {
            "success": True,
            "status": "AUTONOMOUS_TRAINING_CONFIGURATION_UPDATED",
            "operation": "autonomous_learning",
            "training_state": state,
            "auto_training": decision,
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
            "profile_versions": self.store.list_profile_versions(limit=limit),
            "training_state": self.store.get_training_state(),
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
            if subsystem and subsystem in list(item.get("subsystems", [])):
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
            "training_state": self.store.get_training_state(),
            "report_path": str(self.store.path),
            "errors": [],
        }

    @staticmethod
    def _training_status(
        *,
        learned_status: str,
        deployment: dict[str, Any],
        apply: bool,
        automatic: bool,
    ) -> str:
        deployment_status = str(deployment.get("status", ""))
        if bool(deployment.get("applied", False)):
            return (
                "AUTONOMOUS_TRAINING_PROFILE_DEPLOYED"
                if automatic
                else "AUTONOMOUS_LEARNING_PROFILE_APPLIED"
            )
        if apply and deployment_status == "AUTONOMOUS_PROFILE_STAGED":
            return "AUTONOMOUS_LEARNING_PROFILE_STAGED"
        if apply and deployment_status == "AUTONOMOUS_PROFILE_REJECTED":
            return "AUTONOMOUS_LEARNING_PROFILE_REJECTED"
        return learned_status

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
