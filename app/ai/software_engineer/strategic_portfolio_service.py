from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import traceback
from typing import Any

from .strategic_development_service import StrategicDevelopmentService
from .strategic_execution_service import (
    StrategicExecutionService,
    bootstrap_strategic_execution,
)
from .strategic_portfolio_optimizer import StrategicPortfolioOptimizer
from .strategic_portfolio_store import StrategicPortfolioStore


class StrategicPortfolioService:
    """B59 adaptive portfolio rebalancing over B57/B58 outcomes."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        strategic_development: StrategicDevelopmentService | Any,
        strategic_execution: StrategicExecutionService | Any,
        store: StrategicPortfolioStore | None = None,
        optimizer: StrategicPortfolioOptimizer | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.strategic_development = strategic_development
        self.strategic_execution = strategic_execution
        self.store = store or StrategicPortfolioStore(self.project_root)
        self.optimizer = optimizer or StrategicPortfolioOptimizer()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def rebalance(
        self,
        *,
        refresh_roadmap: bool = True,
        reconcile_execution: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            policy = self.store.policy()
            self.store.update_runtime({
                "phase": "REBALANCING",
                "last_error": "",
            })
            try:
                if not bool(policy.get("integrate_with_b57", True)):
                    return self._finish_cycle(
                        "STRATEGIC_PORTFOLIO_B57_INTEGRATION_DISABLED",
                        success=True,
                        phase="READY",
                    )
                if refresh_roadmap or not self.strategic_development.store.summary().get(
                    "total", 0
                ):
                    refreshed = self.strategic_development.refresh()
                    if not bool(refreshed.get("success", False)):
                        return self._finish_cycle(
                            "STRATEGIC_PORTFOLIO_ROADMAP_REFRESH_FAILED",
                            success=False,
                            phase="FAILED",
                            errors=list(refreshed.get("errors", [])),
                            roadmap_refresh=refreshed,
                        )
                if reconcile_execution and bool(
                    policy.get("integrate_with_b58", True)
                ):
                    self.strategic_execution.reconcile(
                        refresh_roadmap=False
                    )
                goals = self.strategic_development.store.list_goals(
                    limit=1000
                )
                executions = self.strategic_execution.store.list_records(
                    limit=10000
                )
                existing = {
                    str(item.get("goal_id", "")): item
                    for item in self.store.list_entries(limit=1000)
                    if str(item.get("goal_id", "")).strip()
                }
                runtime = self.store.runtime()
                entries = self.optimizer.build_entries(
                    goals,
                    executions,
                    existing_by_goal_id=existing,
                    policy=policy,
                    last_selected_subsystem=str(
                        runtime.get("last_selected_subsystem", "")
                    ),
                )
                max_entries = int(policy.get("max_entries", 200))
                saved = self.store.replace_entries(
                    entries[:max_entries]
                )
                candidates = self.optimizer.select_candidates(
                    saved,
                    min_adaptive_score=float(
                        policy.get("min_adaptive_score", 5.0)
                    ),
                )
                selected = candidates[0] if candidates else {}
                result = self._finish_cycle(
                    "STRATEGIC_PORTFOLIO_REBALANCED",
                    success=True,
                    phase="READY",
                    entries=saved[:50],
                    selected=selected,
                    selected_goal_id=str(selected.get("goal_id", "")),
                    last_rebalance_at=self._now(),
                )
                return result
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                self.store.update_runtime({
                    "phase": "FAILED",
                    "last_error": message,
                })
                result = self._response(
                    "STRATEGIC_PORTFOLIO_REBALANCE_FAILED",
                    success=False,
                    errors=[message],
                    traceback=traceback.format_exc()[-12000:],
                )
                self._record(result)
                return result

    def recommend_opportunity(
        self,
        *,
        rebalance_if_due: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            runtime = self.store.runtime()
            policy = self.store.policy()
            if not bool(runtime.get("enabled", False)) or not bool(
                policy.get("enabled", True)
            ):
                return self._response(
                    "STRATEGIC_PORTFOLIO_DISABLED",
                    success=True,
                    selected={},
                    recommendation={},
                )
            if bool(runtime.get("paused", False)):
                return self._response(
                    "STRATEGIC_PORTFOLIO_PAUSED",
                    success=True,
                    selected={},
                    recommendation={},
                )
            if not bool(policy.get("integrate_with_b58", True)):
                return self._response(
                    "STRATEGIC_PORTFOLIO_B58_INTEGRATION_DISABLED",
                    success=True,
                    selected={},
                    recommendation={},
                )
            if rebalance_if_due and self._rebalance_due(runtime, policy):
                balanced = self.rebalance()
                if not bool(balanced.get("success", False)):
                    return balanced

            entries = self.optimizer.select_candidates(
                self.store.list_entries(limit=1000),
                min_adaptive_score=float(
                    policy.get("min_adaptive_score", 5.0)
                ),
            )
            project = self.strategic_development.project_intelligence
            project_policy = project.store.policy()
            opportunities = project.store.list_opportunities(limit=1000)
            strategic_policy = self.strategic_development.store.policy()
            for entry in entries:
                goal_id = str(entry.get("goal_id", "")).strip()
                goal = self.strategic_development.store.get_goal(goal_id)
                if not self._goal_is_dispatchable(goal, strategic_policy):
                    continue
                recommendation = (
                    self.strategic_development.planner.select_opportunity(
                        goal,
                        opportunities,
                        ranker=project.ranker,
                        min_score=float(project_policy.get("min_score", 25.0)),
                        max_risk=min(
                            float(project_policy.get("max_risk", 65.0)),
                            float(
                                strategic_policy.get("max_goal_risk", 65.0)
                            ),
                        ),
                        min_confidence=max(
                            float(
                                project_policy.get("min_confidence", 0.30)
                            ),
                            float(
                                strategic_policy.get(
                                    "min_goal_confidence", 0.30
                                )
                            ),
                        ),
                    )
                )
                opportunity_id = str(
                    recommendation.get("opportunity_id", "")
                    if isinstance(recommendation, dict)
                    else ""
                ).strip()
                if not opportunity_id:
                    continue
                if bool(policy.get("auto_apply_selection", True)):
                    self.strategic_development.store.update_runtime({
                        "active_goal_id": goal_id,
                        "phase": "GOAL_SELECTED_BY_B59",
                        "last_recommendation_id": opportunity_id,
                    })
                updates = {
                    "phase": "RECOMMENDATION_READY",
                    "selected_goal_id": goal_id,
                    "last_selected_subsystem": str(
                        entry.get("subsystem", "")
                    ),
                    "last_result": {
                        "status": "STRATEGIC_PORTFOLIO_RECOMMENDATION_READY",
                        "goal_id": goal_id,
                        "opportunity_id": opportunity_id,
                    },
                    "last_error": "",
                }
                self.store.update_runtime(updates)
                result = self._response(
                    "STRATEGIC_PORTFOLIO_RECOMMENDATION_READY",
                    success=True,
                    selected=goal or {},
                    portfolio_entry=entry,
                    recommendation=recommendation or {},
                )
                self._record(result)
                return result

            self.store.update_runtime({
                "phase": "READY",
                "selected_goal_id": "",
                "last_result": {
                    "status": "STRATEGIC_PORTFOLIO_NO_SAFE_RECOMMENDATION",
                    "success": True,
                },
            })
            result = self._response(
                "STRATEGIC_PORTFOLIO_NO_SAFE_RECOMMENDATION",
                success=True,
                selected={},
                recommendation={},
            )
            self._record(result)
            return result

    def observe_execution(
        self,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        item = dict(execution or {})
        self.store.update_runtime({
            "last_execution_id": str(item.get("execution_id", "")),
            "last_outcome": str(item.get("status", "")).upper(),
            "phase": "LEARNING",
        })
        result = self.rebalance(
            refresh_roadmap=False,
            reconcile_execution=False,
        )
        self.store.record_history({
            "status": "STRATEGIC_PORTFOLIO_EXECUTION_OBSERVED",
            "success": bool(result.get("success", False)),
            "phase": self.store.runtime().get("phase", ""),
            "goal_id": item.get("goal_id", ""),
            "execution_id": item.get("execution_id", ""),
            "outcome": item.get("status", ""),
            "error": item.get("last_error", ""),
        })
        learner = getattr(self, "strategic_policy_evolution_service", None)
        if learner is not None:
            try:
                learner.observe_execution(item)
            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")
        return result

    def start_background(self) -> dict[str, Any]:
        if self.is_running():
            return self._response(
                "STRATEGIC_PORTFOLIO_SUPERVISOR_ALREADY_RUNNING",
                success=True,
            )
        with self._lock:
            if self.is_running():
                return self._response(
                    "STRATEGIC_PORTFOLIO_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            policy = self.store.update_policy({
                "enabled": True,
                "max_active_goals": 1,
                "auto_approve": False,
            })
            self.store.update_runtime({
                "enabled": True,
                "paused": False,
                "running": False,
                "phase": "STARTING",
                "last_error": "",
            })
            if bool(policy.get("start_b58_with_supervisor", True)):
                self.strategic_execution.start()
            self.store.update_runtime({
                "enabled": True,
                "paused": False,
                "running": True,
                "phase": "RUNNING",
                "last_error": "",
            })
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="jarvis-strategic-portfolio",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "STRATEGIC_PORTFOLIO_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        if bool(self.store.runtime().get("enabled", False)):
            return self.start_background()
        return self._response(
            "STRATEGIC_PORTFOLIO_SUPERVISOR_DISABLED",
            success=True,
        )

    def stop_background(self) -> dict[str, Any]:
        self._stop_event.set()
        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=5.0)
        runtime = self.store.update_runtime({
            "enabled": False,
            "paused": False,
            "running": False,
            "phase": "STOPPED",
        })
        return self._response(
            "STRATEGIC_PORTFOLIO_SUPERVISOR_STOPPED",
            success=True,
            runtime=runtime,
        )

    def pause(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "STRATEGIC_PORTFOLIO_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        runtime = self.store.update_runtime({
            "enabled": True,
            "paused": False,
            "phase": "RESUMING",
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            "STRATEGIC_PORTFOLIO_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def status(self) -> dict[str, Any]:
        runtime = self.store.runtime()
        policy = self.store.policy()
        if self._rebalance_due(runtime, policy):
            self.rebalance()
        selected = self.store.get_entry(
            str(self.store.runtime().get("selected_goal_id", ""))
        )
        return self._response(
            "STRATEGIC_PORTFOLIO_STATUS",
            success=True,
            selected=selected or {},
            entries=self.store.list_entries(limit=20),
        )

    def portfolio(self, *, limit: int = 50) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_PORTFOLIO_VIEW",
            success=True,
            entries=self.store.list_entries(limit=limit),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_PORTFOLIO_HISTORY",
            success=True,
            history=self.store.history(limit=limit),
        )

    def update_policy(
        self,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        policy = self.store.update_policy({
            **dict(updates),
            "max_active_goals": 1,
            "auto_approve": False,
        })
        return self._response(
            "STRATEGIC_PORTFOLIO_POLICY_UPDATED",
            success=True,
            policy=policy,
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def is_enabled(self) -> bool:
        runtime = self.store.runtime()
        policy = self.store.policy()
        return bool(
            runtime.get("enabled", False)
            and not runtime.get("paused", False)
            and policy.get("enabled", True)
            and policy.get("integrate_with_b57", True)
            and policy.get("integrate_with_b58", True)
        )

    def _run_loop(self) -> None:
        try:
            if self._stop_event.wait(30.0):
                return

            while not self._stop_event.is_set():
                try:
                    if not bool(self.store.runtime().get("paused", False)):
                        self.rebalance()
                except Exception as error:
                    self.store.update_runtime({
                        "last_error": f"{type(error).__name__}: {error}",
                        "phase": "FAILED",
                    })
                interval = float(
                    self.store.policy().get(
                        "rebalance_interval_seconds", 300.0
                    )
                )
                self._stop_event.wait(max(60.0, interval))
        finally:
            self.store.update_runtime({"running": False})

    def _finish_cycle(
        self,
        status: str,
        *,
        success: bool,
        phase: str,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        runtime = self.store.runtime()
        updates = {
            "phase": phase,
            "cycles_completed": int(runtime.get("cycles_completed", 0)) + 1,
            "last_error": "; ".join(str(item) for item in (errors or [])),
            "last_result": {
                "status": status,
                "success": success,
            },
        }
        for key in (
            "selected_goal_id",
            "last_rebalance_at",
        ):
            if key in extra:
                updates[key] = str(extra.get(key, ""))
        self.store.update_runtime(updates)
        result = self._response(
            status,
            success=success,
            errors=errors,
            **extra,
        )
        self._record(result)
        return result

    def _record(self, response: dict[str, Any]) -> None:
        selected = response.get("selected", {})
        selected = dict(selected) if isinstance(selected, dict) else {}
        recommendation = response.get("recommendation", {})
        recommendation = (
            dict(recommendation)
            if isinstance(recommendation, dict)
            else {}
        )
        errors = response.get("errors", [])
        self.store.record_history({
            "status": response.get("status", "UNKNOWN"),
            "success": bool(response.get("success", False)),
            "phase": self.store.runtime().get("phase", ""),
            "goal_id": selected.get("goal_id", ""),
            "outcome": recommendation.get("opportunity_id", ""),
            "error": "; ".join(str(item) for item in errors[:5])
            if isinstance(errors, list)
            else "",
        })

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "strategic_portfolio",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "summary": self.store.summary(),
            "roadmap_summary": self.strategic_development.store.summary(),
            "execution_summary": self.strategic_execution.store.summary(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    @staticmethod
    def _goal_is_dispatchable(
        goal: dict[str, Any] | None,
        policy: dict[str, Any],
    ) -> bool:
        if not isinstance(goal, dict) or not goal:
            return False
        return bool(
            int(goal.get("pending_count", 0) or 0) > 0
            and float(goal.get("priority_score", 0.0) or 0.0)
            >= float(policy.get("min_goal_score", 15.0))
            and float(goal.get("risk_score", 0.0) or 0.0)
            <= float(policy.get("max_goal_risk", 65.0))
            and float(goal.get("confidence", 0.0) or 0.0)
            >= float(policy.get("min_goal_confidence", 0.30))
        )

    @staticmethod
    def _parse_time(value: Any) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _rebalance_due(
        self,
        runtime: dict[str, Any],
        policy: dict[str, Any],
    ) -> bool:
        last = self._parse_time(runtime.get("last_rebalance_at", ""))
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= float(
            policy.get("rebalance_interval_seconds", 300.0)
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_strategic_portfolio(
    controller: Any,
) -> StrategicPortfolioService:
    service = getattr(controller, "strategic_portfolio_service", None)
    if service is None:
        strategic_execution = bootstrap_strategic_execution(controller)
        strategic_development = strategic_execution.strategic_development
        service = StrategicPortfolioService(
            controller.project_root,
            strategic_development=strategic_development,
            strategic_execution=strategic_execution,
        )
        controller.strategic_portfolio_service = service
        strategic_execution.strategic_portfolio_service = service
        strategic_development.strategic_portfolio_service = service
    service.store.compact()
    service.start_if_enabled()
    return service
