"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.autodev.developer_validator import DeveloperValidator

from .autonomous_campaign_director import AutonomousCampaignDirector
from .autonomous_learning_engine import AutonomousLearningEngine
from .full_autonomy_execution_tracker import FullAutonomyExecutionTracker
from .full_autonomy_planner import FullAutonomyPlanner
from .full_autonomy_store import FullAutonomyStore
from .multi_campaign_workflow import MultiCampaignWorkflow
from .portfolio_optimizer import PortfolioOptimizer


class FullAutonomyWorkflow:
    """Executes one large goal from autonomous plan to final report."""

    TERMINAL_STATUSES = {
        "FULL_AUTONOMY_COMPLETED",
        "FULL_AUTONOMY_FAILED",
        "FULL_AUTONOMY_ROLLED_BACK",
        "FULL_AUTONOMY_FINAL_VALIDATION_FAILED",
        "FULL_AUTONOMY_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        planner: FullAutonomyPlanner | Any | None = None,
        portfolio_workflow: MultiCampaignWorkflow | Any | None = None,
        optimizer: PortfolioOptimizer | Any | None = None,
        director: AutonomousCampaignDirector | Any | None = None,
        validator: DeveloperValidator | Any | None = None,
        store: FullAutonomyStore | None = None,
        learning_engine: AutonomousLearningEngine | Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.planner = planner or FullAutonomyPlanner(self.project_root)
        self.portfolio_workflow = portfolio_workflow or MultiCampaignWorkflow(
            self.project_root
        )
        self.optimizer = optimizer or PortfolioOptimizer(
            self.project_root,
            store=self.portfolio_workflow.store,
        )
        self.director = director or AutonomousCampaignDirector(
            self.project_root,
            workflow=self.portfolio_workflow,
            optimizer=self.optimizer,
        )
        self.validator = validator or DeveloperValidator(
            project_root=self.project_root
        )
        self.store = store or FullAutonomyStore(self.project_root)
        self.learning_engine = learning_engine or AutonomousLearningEngine(
            self.project_root
        )
        self.tracker = FullAutonomyExecutionTracker(
            self.project_root,
            portfolio_workflow=self.portfolio_workflow,
        )

    def run(
        self,
        objective: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = self._apply_learning_policy(
            dict(context or {})
        )
        run_id = self._safe_run_id(
            values.get("autonomy_run_id")
            or values.get("run_id")
            or f"autonomy-{uuid4().hex}"
        )
        existing = self.store.get(run_id)
        if existing is not None:
            return {
                **self._response(existing),
                "success": False,
                "status": "FULL_AUTONOMY_RUN_ALREADY_EXISTS",
                "errors": [
                    "Przebieg pełnej autonomii o tym run_id już istnieje."
                ],
            }
        run = self._new_run(
            run_id,
            objective,
            values,
        )
        self._event(run, "AUTONOMY_STARTED")
        self.store.save(run)

        try:
            plan = self.planner.plan(
                objective,
                targets=values.get(
                    "autonomy_targets",
                    values.get("targets"),
                ),
                campaigns=values.get(
                    "autonomy_campaigns",
                    values.get("portfolio_campaigns"),
                ),
                replacements=(
                    values.get("replacements")
                    if isinstance(values.get("replacements"), dict)
                    else None
                ),
                goal_id=values.get("goal_id"),
                portfolio_id=values.get("portfolio_id"),
                acceptance_criteria=values.get("acceptance_criteria"),
                metadata=dict(values.get("autonomy_metadata", {}) or {}),
            )
        except Exception as error:
            return self._fail(
                run,
                status="FULL_AUTONOMY_PLANNING_FAILED",
                errors=[f"{type(error).__name__}: {error}"],
            )

        run["goal_id"] = plan.goal_id
        run["portfolio_id"] = plan.portfolio_id
        run["plan"] = plan.to_dict()
        run["status"] = "FULL_AUTONOMY_PLAN_READY"
        self._event(
            run,
            "AUTONOMY_PLAN_READY",
            {
                "campaign_count": len(plan.campaigns),
                "target_count": len(plan.target_files),
            },
        )
        self.store.save(run)

        try:
            portfolio_response = self.portfolio_workflow.run(
                plan.objective,
                campaigns=plan.campaigns,
                portfolio_id=plan.portfolio_id,
                auto_execute=False,
                auto_approve=bool(values.get("auto_approve", False)),
                auto_rollback=bool(values.get("auto_rollback", True)),
                final_validation=bool(values.get("final_validation", True)),
                continue_on_failure=True,
                rollback_completed_on_failure=False,
                metadata={
                    "full_autonomy": True,
                    "full_autonomy_run_id": run_id,
                    "goal_id": plan.goal_id,
                    "plan_fingerprint": plan.fingerprint,
                },
            )
        except Exception as error:
            return self._fail(
                run,
                status="FULL_AUTONOMY_PORTFOLIO_FAILED",
                errors=[f"{type(error).__name__}: {error}"],
            )

        if not bool(portfolio_response.get("success", False)):
            return self._fail(
                run,
                status="FULL_AUTONOMY_PORTFOLIO_FAILED",
                errors=[
                    str(item)
                    for item in portfolio_response.get("errors", [])
                ] or [
                    str(portfolio_response.get("status", "Portfolio failed"))
                ],
            )

        run["portfolio"] = dict(portfolio_response.get("portfolio", {}) or {})
        run["status"] = "FULL_AUTONOMY_PORTFOLIO_READY"
        self._event(run, "AUTONOMY_PORTFOLIO_READY")
        self._update_execution(
            run,
            event="AUTONOMY_PORTFOLIO_READY",
        )
        self.store.save(run)

        plan_only = bool(
            values.get("plan_only", False)
            or not values.get("auto_execute", True)
        )
        optimization = self._optimize(
            plan.portfolio_id,
            values,
        )
        run["optimization"] = optimization
        self.store.save(run)

        if plan_only:
            run["status"] = "FULL_AUTONOMY_PLAN_READY"
            run["success"] = True
            run["completed_at"] = self._now()
            self._event(run, "AUTONOMY_PLAN_ONLY_COMPLETED")
            self._update_execution(
                run,
                event="AUTONOMY_PLAN_ONLY_COMPLETED",
            )
            return self._response(self.store.save(run))

        run["status"] = "FULL_AUTONOMY_RUNNING"
        run["success"] = False
        self._event(run, "AUTONOMY_DIRECTOR_STARTED")
        self._update_execution(
            run,
            event="AUTONOMY_DIRECTOR_STARTED",
        )
        self.store.save(run)
        try:
            director_result = self.director.direct(
                plan.portfolio_id,
                constraints=self._constraints(values),
                auto_approve=values.get("auto_approve"),
                auto_rollback=values.get("auto_rollback"),
                final_validation=values.get("final_validation"),
                max_cycles=self._bounded_int(
                    values.get("max_cycles", 50),
                    minimum=1,
                    maximum=100,
                ),
                max_retries_per_campaign=self._bounded_int(
                    values.get("max_retries_per_campaign", 1),
                    minimum=0,
                    maximum=5,
                ),
                max_failures=self._bounded_int(
                    values.get("max_failures", 3),
                    minimum=1,
                    maximum=30,
                ),
                rollback_on_stop=bool(
                    values.get("rollback_on_stop", True)
                ),
                progress_callback=self._progress_callback(
                    run
                ),
            )
        except Exception as error:
            return self._fail(
                run,
                status="FULL_AUTONOMY_DIRECTOR_EXCEPTION",
                errors=[f"{type(error).__name__}: {error}"],
                rollback=bool(values.get("auto_rollback", True)),
            )

        run["director_result"] = dict(director_result)
        run["director_run_id"] = str(
            director_result.get("director_run", {}).get("run_id", "")
            if isinstance(director_result.get("director_run"), dict)
            else ""
        )
        run["portfolio"] = dict(director_result.get("portfolio", {}) or {})
        self._event(
            run,
            "AUTONOMY_DIRECTOR_FINISHED",
            {"status": str(director_result.get("status", "UNKNOWN"))},
        )
        self._update_execution(
            run,
            event="AUTONOMY_DIRECTOR_FINISHED",
            metadata={
                "director_status": str(
                    director_result.get(
                        "status",
                        "UNKNOWN",
                    )
                ),
            },
        )
        self.store.save(run)

        if not self._director_completed(director_result):
            paused = self._director_paused(director_result)
            run["success"] = bool(paused)
            run["status"] = (
                "FULL_AUTONOMY_PAUSED"
                if paused
                else "FULL_AUTONOMY_FAILED"
            )
            run["errors"].extend(
                str(item)
                for item in director_result.get("errors", [])
            )
            if not paused:
                run["completed_at"] = self._now()
            self._event(
                run,
                "AUTONOMY_PAUSED" if paused else "AUTONOMY_FAILED"
            )
            self._update_execution(
                run,
                event=(
                    "AUTONOMY_PAUSED"
                    if paused
                    else "AUTONOMY_FAILED"
                ),
            )
            return self._response(self.store.save(run))

        return self._finalize(
            run,
            auto_rollback=bool(values.get("auto_rollback", True)),
            final_validation=bool(values.get("final_validation", True)),
        )

    def resume(
        self,
        run_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = self.store.get(run_id)
        if run is None:
            return self._not_found(run_id)
        if str(run.get("status", "")) in self.TERMINAL_STATUSES:
            return self._response(run)

        values = {
            **dict(run.get("policy", {}) or {}),
            **dict(context or {}),
        }
        values = self._apply_learning_policy(values)
        values["auto_execute"] = True
        run["policy"] = {
            **dict(run.get("policy", {}) or {}),
            "auto_execute": True,
            "auto_approve": bool(
                values.get("auto_approve", False)
            ),
            "auto_rollback": bool(
                values.get("auto_rollback", True)
            ),
            "final_validation": bool(
                values.get("final_validation", True)
            ),
            "max_cycles": self._bounded_int(
                values.get("max_cycles", 50),
                minimum=1,
                maximum=100,
            ),
            "max_retries_per_campaign": self._bounded_int(
                values.get(
                    "max_retries_per_campaign",
                    1,
                ),
                minimum=0,
                maximum=5,
            ),
            "max_failures": self._bounded_int(
                values.get("max_failures", 3),
                minimum=1,
                maximum=30,
            ),
            "rollback_on_stop": bool(
                values.get("rollback_on_stop", True)
            ),
            "optimization_constraints": self._constraints(
                values
            ),
        }
        run["completed_at"] = ""
        portfolio_id = str(run.get("portfolio_id", "")).strip()
        if not portfolio_id:
            return self._fail(
                run,
                status="FULL_AUTONOMY_RESUME_INVALID_STATE",
                errors=["Przebieg nie ma portfolio_id."],
            )

        run["status"] = "FULL_AUTONOMY_RUNNING"
        run["success"] = False
        self._event(run, "AUTONOMY_RESUMED")
        self._update_execution(
            run,
            event="AUTONOMY_RESUMED",
        )
        self.store.save(run)
        try:
            result = self.director.direct(
                portfolio_id,
                constraints=self._constraints(values),
                auto_approve=values.get("auto_approve"),
                auto_rollback=values.get("auto_rollback"),
                final_validation=values.get("final_validation"),
                max_cycles=self._bounded_int(
                    values.get("max_cycles", 50),
                    minimum=1,
                    maximum=100,
                ),
                max_retries_per_campaign=self._bounded_int(
                    values.get("max_retries_per_campaign", 1),
                    minimum=0,
                    maximum=5,
                ),
                max_failures=self._bounded_int(
                    values.get("max_failures", 3),
                    minimum=1,
                    maximum=30,
                ),
                rollback_on_stop=bool(
                    values.get("rollback_on_stop", True)
                ),
                progress_callback=self._progress_callback(
                    run
                ),
            )
        except Exception as error:
            return self._fail(
                run,
                status="FULL_AUTONOMY_DIRECTOR_EXCEPTION",
                errors=[f"{type(error).__name__}: {error}"],
                rollback=bool(values.get("auto_rollback", True)),
            )

        run["director_result"] = dict(result)
        run["portfolio"] = dict(result.get("portfolio", {}) or {})
        run["director_run_id"] = str(
            result.get("director_run", {}).get("run_id", "")
            if isinstance(result.get("director_run"), dict)
            else ""
        )
        self._update_execution(
            run,
            event="AUTONOMY_RESUME_DIRECTOR_FINISHED",
            metadata={
                "director_status": str(
                    result.get(
                        "status",
                        "UNKNOWN",
                    )
                ),
            },
        )
        self.store.save(run)
        if self._director_completed(result):
            return self._finalize(
                run,
                auto_rollback=bool(values.get("auto_rollback", True)),
                final_validation=bool(values.get("final_validation", True)),
            )

        paused = self._director_paused(result)
        run["success"] = bool(paused)
        run["status"] = (
            "FULL_AUTONOMY_PAUSED"
            if paused
            else "FULL_AUTONOMY_FAILED"
        )
        if not paused:
            run["completed_at"] = self._now()
        run["errors"].extend(
            str(item)
            for item in result.get("errors", [])
        )
        self._update_execution(
            run,
            event=(
                "AUTONOMY_PAUSED"
                if paused
                else "AUTONOMY_FAILED"
            ),
        )
        return self._response(self.store.save(run))

    def rollback(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        run = self.store.get(run_id)
        if run is None:
            return self._not_found(run_id)
        portfolio_id = str(run.get("portfolio_id", "")).strip()
        if not portfolio_id:
            return self._fail(
                run,
                status="FULL_AUTONOMY_ROLLBACK_INVALID_STATE",
                errors=["Przebieg nie ma portfolio_id."],
            )
        result = self._safe_rollback(portfolio_id)
        run["rollback"] = dict(result)
        run["success"] = bool(result.get("success", False))
        run["status"] = (
            "FULL_AUTONOMY_ROLLED_BACK"
            if run["success"]
            else "FULL_AUTONOMY_ROLLBACK_FAILED"
        )
        run["completed_at"] = self._now()
        run["errors"].extend(
            str(item)
            for item in result.get("errors", [])
        )
        self._event(run, "AUTONOMY_ROLLBACK_FINISHED")
        self._update_execution(
            run,
            event="AUTONOMY_ROLLBACK_FINISHED",
        )
        return self._response(self.store.save(run))

    def status(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        run = self.store.get(run_id)

        if run is None:
            return self._not_found(run_id)

        self._update_execution(
            run,
            event="",
        )
        return self._response(
            self.store.save(run)
        )

    def execute(
        self,
        run_id: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = self.store.get(run_id)

        if run is None:
            return self._not_found(run_id)

        status = str(
            run.get(
                "status",
                "",
            )
        ).upper()

        if status in self.TERMINAL_STATUSES:
            return self._response(run)

        if status not in {
            "FULL_AUTONOMY_PLAN_READY",
            "FULL_AUTONOMY_PORTFOLIO_READY",
            "FULL_AUTONOMY_PAUSED",
            "FULL_AUTONOMY_RUNNING",
        }:
            return {
                **self._response(run),
                "success": False,
                "status": "FULL_AUTONOMY_EXECUTION_INVALID_STATE",
                "errors": [
                    "Przebieg nie jest gotowy do wykonania.",
                ],
            }

        values = dict(
            context or {}
        )
        values["auto_execute"] = True

        return self.resume(
            run_id,
            context=values,
        )

    def pause(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        run = self.store.get(run_id)

        if run is None:
            return self._not_found(run_id)

        portfolio_id = str(
            run.get(
                "portfolio_id",
                "",
            )
        ).strip()

        if not portfolio_id:
            return self._fail(
                run,
                status="FULL_AUTONOMY_PAUSE_INVALID_STATE",
                errors=["Przebieg nie ma portfolio_id."],
            )

        try:
            result = self.portfolio_workflow.pause(
                portfolio_id
            )
        except Exception as error:
            return self._fail(
                run,
                status="FULL_AUTONOMY_PAUSE_FAILED",
                errors=[
                    f"{type(error).__name__}: {error}",
                ],
            )

        run["portfolio"] = dict(
            result.get(
                "portfolio",
                {},
            )
            or {}
        )
        run["status"] = "FULL_AUTONOMY_PAUSED"
        run["success"] = True
        self._event(
            run,
            "AUTONOMY_PAUSED_MANUALLY",
        )
        self._update_execution(
            run,
            event="AUTONOMY_PAUSED_MANUALLY",
        )
        return self._response(
            self.store.save(run)
        )

    def recent(
        self,
        *,
        limit: int = 20,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "status": "FULL_AUTONOMY_RECENT",
            "operation": "full_autonomy",
            "autonomy_run_id": "",
            "autonomy_run": {},
            "autonomy_runs": self.store.list_recent(limit=limit),
            "errors": [],
            "report_path": str(self.store.path),
        }

    def _finalize(
        self,
        run: dict[str, Any],
        *,
        auto_rollback: bool,
        final_validation: bool,
    ) -> dict[str, Any]:
        run["status"] = "FULL_AUTONOMY_FINAL_VALIDATION_RUNNING"
        self._update_execution(
            run,
            event="AUTONOMY_FINAL_VALIDATION_STARTED",
        )
        self.store.save(run)
        validation = (
            self._validate(run)
            if final_validation
            else {
                "success": True,
                "status": "FULL_AUTONOMY_VALIDATION_SKIPPED",
                "errors": [],
            }
        )
        run["final_validation"] = validation
        self._event(
            run,
            "AUTONOMY_FINAL_VALIDATION",
            {"success": bool(validation.get("success", False))},
        )

        if not bool(validation.get("success", False)):
            run["errors"].extend(
                str(item)
                for item in validation.get("errors", [])
            )
            run["status"] = "FULL_AUTONOMY_FINAL_VALIDATION_FAILED"
            run["success"] = False
            if auto_rollback:
                rollback = self._safe_rollback(
                    str(run.get("portfolio_id", ""))
                )
                run["rollback"] = dict(rollback)
                if bool(rollback.get("success", False)):
                    run["status"] = (
                        "FULL_AUTONOMY_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK"
                    )
            run["completed_at"] = self._now()
            self._event(run, "AUTONOMY_FINAL_VALIDATION_FAILED")
            self._update_execution(
                run,
                event="AUTONOMY_FINAL_VALIDATION_FAILED",
            )
            return self._response(self._save_terminal(run))

        run["success"] = True
        run["status"] = "FULL_AUTONOMY_COMPLETED"
        run["completed_at"] = self._now()
        self._update_execution(
            run,
            event="AUTONOMY_COMPLETED",
        )
        run["final_report"] = self._report(run)
        self._event(run, "AUTONOMY_COMPLETED")
        return self._response(self._save_terminal(run))

    def _validate(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        plan = dict(run.get("plan", {}) or {})
        try:
            result = self.validator.run_test_suite(
                changed_files=list(plan.get("target_files", [])),
                full_suite=True,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "FULL_AUTONOMY_VALIDATION_EXCEPTION",
                "errors": [f"{type(error).__name__}: {error}"],
            }
        value = (
            result.as_dict()
            if hasattr(result, "as_dict")
            else dict(result)
            if isinstance(result, dict)
            else {
                "success": False,
                "errors": ["Walidator zwrócił nieprawidłowy wynik."],
            }
        )
        value.setdefault(
            "status",
            "FULL_AUTONOMY_VALIDATION_PASSED"
            if value.get("success", False)
            else "FULL_AUTONOMY_VALIDATION_FAILED",
        )
        value.setdefault("errors", [])
        return value

    def _optimize(
        self,
        portfolio_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            result = self.director.optimize(
                portfolio_id,
                constraints=self._constraints(values),
                apply=True,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "FULL_AUTONOMY_OPTIMIZATION_EXCEPTION",
                "errors": [f"{type(error).__name__}: {error}"],
            }
        return dict(result.get("optimization", {}) or result)

    def _safe_rollback(
        self,
        portfolio_id: str,
    ) -> dict[str, Any]:
        try:
            return dict(
                self.portfolio_workflow.rollback(
                    portfolio_id
                )
            )
        except Exception as error:
            return {
                "success": False,
                "status": "FULL_AUTONOMY_ROLLBACK_EXCEPTION",
                "errors": [f"{type(error).__name__}: {error}"],
            }

    def _fail(
        self,
        run: dict[str, Any],
        *,
        status: str,
        errors: list[str],
        rollback: bool = False,
    ) -> dict[str, Any]:
        run["success"] = False
        run["status"] = str(status)
        run["errors"].extend(str(item) for item in errors)
        if rollback and run.get("portfolio_id"):
            try:
                run["rollback"] = dict(
                    self.portfolio_workflow.rollback(
                        str(run["portfolio_id"])
                    )
                )
            except Exception as error:
                run["errors"].append(
                    f"Rollback error: {type(error).__name__}: {error}"
                )
        run["completed_at"] = self._now()
        self._event(run, "AUTONOMY_FAILED", {"status": status})
        self._update_execution(
            run,
            event="AUTONOMY_FAILED",
            metadata={"status": status},
        )
        return self._response(self._save_terminal(run))

    def _save_terminal(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        saved = self.store.save(run)

        try:
            observation = self.learning_engine.observe_run(saved)
        except Exception as error:
            observation = {
                "success": False,
                "status": "AUTONOMOUS_LEARNING_OBSERVATION_FAILED",
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
            }

        saved["learning_observation"] = dict(observation)
        return self.store.save(saved)

    def _apply_learning_policy(
        self,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(values)

        if result.get("disable_learning_profile") is True:
            return result

        try:
            profile = self.learning_engine.store.get_profile()
        except Exception:
            return result

        if not bool(profile.get("active", False)):
            return result

        director_policy = dict(
            profile.get("director_policy", {})
            if isinstance(profile.get("director_policy"), dict)
            else {}
        )
        for key in (
            "max_retries_per_campaign",
            "max_failures",
            "rollback_on_stop",
        ):
            if key not in result and key in director_policy:
                result[key] = director_policy[key]

        learned_constraints = dict(
            profile.get("optimizer_constraints", {})
            if isinstance(profile.get("optimizer_constraints"), dict)
            else {}
        )
        learned_weights = dict(
            profile.get("optimizer_weights", {})
            if isinstance(profile.get("optimizer_weights"), dict)
            else {}
        )
        current_constraints = self._constraints(result)
        merged_constraints = {
            **learned_constraints,
            **current_constraints,
        }
        if (
            "weights" not in current_constraints
            and learned_weights
        ):
            merged_constraints["weights"] = learned_weights

        result["optimization_constraints"] = merged_constraints
        result["learning_profile"] = {
            "active": True,
            "confidence": float(
                profile.get("confidence", 0.0) or 0.0
            ),
            "observations": int(
                profile.get("observations", 0) or 0
            ),
            "source_training_run_id": str(
                profile.get("source_training_run_id", "")
            ),
        }
        return result

    def _new_run(
        self,
        run_id: str,
        objective: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        policy = {
            "auto_execute": bool(values.get("auto_execute", True)),
            "auto_approve": bool(values.get("auto_approve", False)),
            "auto_rollback": bool(values.get("auto_rollback", True)),
            "final_validation": bool(values.get("final_validation", True)),
            "max_cycles": self._bounded_int(
                values.get("max_cycles", 50),
                minimum=1,
                maximum=100,
            ),
            "max_retries_per_campaign": self._bounded_int(
                values.get("max_retries_per_campaign", 1),
                minimum=0,
                maximum=5,
            ),
            "max_failures": self._bounded_int(
                values.get("max_failures", 3),
                minimum=1,
                maximum=30,
            ),
            "rollback_on_stop": bool(
                values.get("rollback_on_stop", True)
            ),
            "optimization_constraints": self._constraints(values),
        }
        return {
            "run_id": run_id,
            "goal_id": "",
            "portfolio_id": "",
            "director_run_id": "",
            "objective": " ".join(str(objective).split()).strip(),
            "status": "FULL_AUTONOMY_STARTING",
            "success": False,
            "started_at": self._now(),
            "updated_at": "",
            "completed_at": "",
            "policy": policy,
            "plan": {},
            "portfolio": {},
            "optimization": {},
            "director_result": {},
            "final_validation": {},
            "rollback": {},
            "final_report": {},
            "execution": {
                "status": "STARTING",
                "phase": "PLANNING",
                "progress_percent": 0.0,
                "campaigns_total": 0,
                "campaigns_completed": 0,
                "campaigns_failed": 0,
                "stages_total": 0,
                "stages_completed": 0,
                "current_campaign_id": "",
                "current_stage_id": "",
                "changed_files": [],
                "started_at": self._now(),
                "updated_at": self._now(),
                "last_checkpoint": {},
                "checkpoints": [],
            },
            "events": [],
            "errors": [],
        }

    def _report(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        plan = dict(run.get("plan", {}) or {})
        director = dict(run.get("director_result", {}) or {})
        director_run = dict(director.get("director_run", {}) or {})
        portfolio = dict(director.get("portfolio", {}) or run.get("portfolio", {}) or {})
        return {
            "objective": str(run.get("objective", "")),
            "goal_id": str(run.get("goal_id", "")),
            "run_id": str(run.get("run_id", "")),
            "portfolio_id": str(run.get("portfolio_id", "")),
            "campaigns_planned": len(plan.get("campaigns", [])),
            "campaigns_completed": len(
                portfolio.get("completed_campaign_ids", [])
            ),
            "targets_count": len(plan.get("target_files", [])),
            "subsystems": list(plan.get("subsystems", [])),
            "director_cycles": int(director_run.get("cycles", 0) or 0),
            "director_retries": int(director_run.get("retries", 0) or 0),
            "optimization_score": float(
                run.get("optimization", {}).get("average_score", 0.0)
                if isinstance(run.get("optimization"), dict)
                else 0.0
            ),
            "acceptance_criteria": list(
                plan.get("acceptance_criteria", [])
            ),
            "final_validation": dict(run.get("final_validation", {}) or {}),
            "execution": dict(run.get("execution", {}) or {}),
            "changed_files": list(
                run.get("execution", {}).get(
                    "changed_files",
                    [],
                )
                if isinstance(
                    run.get("execution"),
                    dict,
                )
                else []
            ),
            "report_path": str(self.store.path),
        }

    def _progress_callback(
        self,
        run: dict[str, Any],
    ):
        def callback(
            event: str,
            payload: dict[str, Any],
        ) -> None:
            if isinstance(
                payload.get(
                    "portfolio",
                ),
                dict,
            ):
                run["portfolio"] = dict(
                    payload["portfolio"]
                )
            if isinstance(
                payload.get(
                    "director_run",
                ),
                dict,
            ):
                run["director_result"] = {
                    **dict(
                        run.get(
                            "director_result",
                            {},
                        )
                        or {}
                    ),
                    "director_run": dict(
                        payload["director_run"]
                    ),
                }
            run["status"] = "FULL_AUTONOMY_RUNNING"
            self._event(
                run,
                str(event),
                dict(
                    payload.get(
                        "metadata",
                        {},
                    )
                    or {}
                ),
            )
            self._update_execution(
                run,
                event=str(event),
                metadata=dict(
                    payload.get(
                        "metadata",
                        {},
                    )
                    or {}
                ),
            )
            self.store.save(run)

        return callback

    def _update_execution(
        self,
        run: dict[str, Any],
        *,
        event: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            run["execution"] = self.tracker.snapshot(
                run,
                event=event,
                metadata=metadata,
            )
        except Exception as error:
            execution = dict(
                run.get(
                    "execution",
                    {},
                )
                or {}
            )
            execution["status"] = str(
                run.get(
                    "status",
                    "UNKNOWN",
                )
            )
            execution["updated_at"] = self._now()
            execution["tracker_error"] = (
                f"{type(error).__name__}: {error}"
            )
            run["execution"] = execution

    @staticmethod
    def _director_completed(
        value: dict[str, Any],
    ) -> bool:
        return (
            bool(value.get("success", False))
            and str(value.get("status", "")).upper()
            == "MULTI_CAMPAIGN_COMPLETED"
        )

    @staticmethod
    def _director_paused(
        value: dict[str, Any],
    ) -> bool:
        status = str(value.get("status", "")).upper()
        return bool(value.get("success", False)) and (
            "PAUSED" in status
            or status == "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS"
        )

    @staticmethod
    def _constraints(
        values: dict[str, Any],
    ) -> dict[str, Any]:
        result = values.get(
            "optimization_constraints",
            values.get("constraints", {}),
        )
        return dict(result) if isinstance(result, dict) else {}

    @staticmethod
    def _bounded_int(
        value: Any,
        *,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = minimum
        return min(maximum, max(minimum, number))

    @staticmethod
    def _safe_run_id(
        value: Any,
    ) -> str:
        text = "".join(
            character
            if character.isalnum() or character in "-_"
            else "-"
            for character in str(value).strip()
        ).strip("-_")
        if not text:
            raise ValueError("run_id pełnej autonomii jest pusty.")
        return text[:120]

    @staticmethod
    def _event(
        run: dict[str, Any],
        event: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        events = run.setdefault("events", [])
        events.append(
            {
                "event": str(event),
                "timestamp": FullAutonomyWorkflow._now(),
                "status": str(run.get("status", "")),
                "metadata": dict(metadata or {}),
            }
        )
        if len(events) > 300:
            del events[:-300]

    def _response(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "success": bool(run.get("success", False)),
            "status": str(run.get("status", "UNKNOWN")),
            "operation": "full_autonomy",
            "autonomy_run_id": str(run.get("run_id", "")),
            "goal_id": str(run.get("goal_id", "")),
            "portfolio_id": str(run.get("portfolio_id", "")),
            "autonomy_run": dict(run),
            "plan": dict(run.get("plan", {}) or {}),
            "portfolio": dict(run.get("portfolio", {}) or {}),
            "optimization": dict(run.get("optimization", {}) or {}),
            "director_run": dict(
                run.get("director_result", {}).get("director_run", {})
                if isinstance(run.get("director_result"), dict)
                else {}
            ),
            "final_validation": dict(run.get("final_validation", {}) or {}),
            "rollback": dict(run.get("rollback", {}) or {}),
            "final_report": dict(run.get("final_report", {}) or {}),
            "execution": dict(run.get("execution", {}) or {}),
            "errors": list(run.get("errors", [])),
            "report_path": str(self.store.path),
        }

    @staticmethod
    def _not_found(
        run_id: str,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "status": "FULL_AUTONOMY_RUN_NOT_FOUND",
            "operation": "full_autonomy",
            "autonomy_run_id": str(run_id),
            "autonomy_run": {},
            "errors": ["Nie znaleziono przebiegu pełnej autonomii."],
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
