from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import traceback
from typing import Any

from .project_intelligence_service import (
    ProjectIntelligenceService,
    bootstrap_project_intelligence,
)
from .self_directed_development_service import (
    SelfDirectedDevelopmentService,
    bootstrap_self_directed_development,
)
from .strategic_development_planner import StrategicDevelopmentPlanner
from .strategic_development_store import StrategicDevelopmentStore


class StrategicDevelopmentService:
    """B57 persistent strategic goals and B56 dispatch guidance."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        project_intelligence: ProjectIntelligenceService | Any,
        self_directed: SelfDirectedDevelopmentService | Any,
        store: StrategicDevelopmentStore | None = None,
        planner: StrategicDevelopmentPlanner | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.project_intelligence = project_intelligence
        self.self_directed = self_directed
        self.store = store or StrategicDevelopmentStore(self.project_root)
        self.planner = planner or StrategicDevelopmentPlanner()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def refresh(self) -> dict[str, Any]:
        with self._lock:
            self.store.update_runtime({
                "running": self.is_running(),
                "phase": "REFRESHING",
                "last_error": "",
            })
            try:
                reconciliation = self.project_intelligence.reconcile()
                opportunities = (
                    self.project_intelligence.store.list_opportunities(
                        limit=1000
                    )
                )
                existing = {
                    str(item.get("fingerprint", "")): item
                    for item in self.store.list_goals(limit=1000)
                    if str(item.get("fingerprint", "")).strip()
                }
                planned = self.planner.build_goals(
                    opportunities,
                    existing_by_fingerprint=existing,
                )
                max_goals = int(self.store.policy().get("max_goals", 100))
                saved = self.store.replace_goals(planned[:max_goals])
                runtime = self.store.runtime()
                result = self._response(
                    "STRATEGIC_DEVELOPMENT_ROADMAP_REFRESHED",
                    success=True,
                    goals=saved[:50],
                    reconciliation=reconciliation,
                )
                self.store.update_runtime({
                    "phase": "READY",
                    "cycles_completed": int(
                        runtime.get("cycles_completed", 0)
                    ) + 1,
                    "last_refresh_at": self._now(),
                    "last_result": self._result_summary(result),
                    "last_error": "",
                })
                self._record(result)
                return self._response(
                    result["status"],
                    success=True,
                    goals=saved[:50],
                    reconciliation=reconciliation,
                )
            except Exception as error:
                message = f"{type(error).__name__}: {error}"
                self.store.update_runtime({
                    "phase": "FAILED",
                    "last_error": message,
                    "last_result": {
                        "status": "STRATEGIC_DEVELOPMENT_REFRESH_FAILED",
                        "success": False,
                    },
                })
                result = self._response(
                    "STRATEGIC_DEVELOPMENT_REFRESH_FAILED",
                    success=False,
                    errors=[message],
                    traceback=traceback.format_exc()[-12000:],
                )
                self._record(result)
                return result

    def select_goal(self) -> dict[str, Any]:
        with self._lock:
            policy = self.store.policy()
            selected = self.planner.select_goal(
                self.store.list_goals(limit=1000),
                min_score=float(policy.get("min_goal_score", 15.0)),
                max_risk=float(policy.get("max_goal_risk", 65.0)),
                min_confidence=float(
                    policy.get("min_goal_confidence", 0.30)
                ),
            )
            goal_id = str(
                selected.get("goal_id", "")
                if isinstance(selected, dict)
                else ""
            ).strip()
            if goal_id and bool(policy.get("auto_select", True)):
                self.store.update_runtime({
                    "active_goal_id": goal_id,
                    "phase": "GOAL_SELECTED",
                })
            return self._response(
                (
                    "STRATEGIC_DEVELOPMENT_GOAL_SELECTED"
                    if selected
                    else "STRATEGIC_DEVELOPMENT_NO_SAFE_GOAL"
                ),
                success=True,
                selected=selected or {},
            )

    def recommend_opportunity(
        self,
        *,
        refresh_if_due: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            runtime = self.store.runtime()
            policy = self.store.policy()
            if not bool(runtime.get("enabled", False)):
                return self._response(
                    "STRATEGIC_DEVELOPMENT_DISABLED",
                    success=True,
                    selected={},
                    recommendation={},
                )
            if bool(runtime.get("paused", False)):
                return self._response(
                    "STRATEGIC_DEVELOPMENT_PAUSED",
                    success=True,
                    selected={},
                    recommendation={},
                )
            if refresh_if_due and self._refresh_due(runtime, policy):
                refreshed = self.refresh()
                if not bool(refreshed.get("success", False)):
                    return refreshed

            goal_id = str(runtime.get("active_goal_id", "")).strip()
            goal = self.store.get_goal(goal_id) if goal_id else None
            if not self._goal_is_dispatchable(goal, policy):
                goal = self.select_goal().get("selected", {})
            if not isinstance(goal, dict) or not goal:
                return self._response(
                    "STRATEGIC_DEVELOPMENT_NO_SAFE_GOAL",
                    success=True,
                    selected={},
                    recommendation={},
                )

            project_policy = self.project_intelligence.store.policy()
            opportunities = (
                self.project_intelligence.store.list_opportunities(
                    limit=1000
                )
            )
            recommendation = self.planner.select_opportunity(
                goal,
                opportunities,
                ranker=self.project_intelligence.ranker,
                min_score=float(project_policy.get("min_score", 25.0)),
                max_risk=min(
                    float(project_policy.get("max_risk", 65.0)),
                    float(policy.get("max_goal_risk", 65.0)),
                ),
                min_confidence=max(
                    float(project_policy.get("min_confidence", 0.30)),
                    float(policy.get("min_goal_confidence", 0.30)),
                ),
            )
            opportunity_id = str(
                recommendation.get("opportunity_id", "")
                if isinstance(recommendation, dict)
                else ""
            ).strip()
            self.store.update_runtime({
                "phase": (
                    "RECOMMENDATION_READY" if opportunity_id else "IDLE"
                ),
                "active_goal_id": str(goal.get("goal_id", "")),
                "last_recommendation_id": opportunity_id,
                "last_result": {
                    "status": (
                        "STRATEGIC_DEVELOPMENT_RECOMMENDATION_READY"
                        if opportunity_id
                        else "STRATEGIC_DEVELOPMENT_NO_SAFE_OPPORTUNITY"
                    ),
                    "goal_id": str(goal.get("goal_id", "")),
                    "opportunity_id": opportunity_id,
                },
            })
            result = self._response(
                (
                    "STRATEGIC_DEVELOPMENT_RECOMMENDATION_READY"
                    if opportunity_id
                    else "STRATEGIC_DEVELOPMENT_NO_SAFE_OPPORTUNITY"
                ),
                success=True,
                selected=goal,
                recommendation=recommendation or {},
            )
            self._record(result)
            return result

    def run_cycle(self) -> dict[str, Any]:
        refreshed = self.refresh()
        if not bool(refreshed.get("success", False)):
            return refreshed
        selected = self.select_goal()
        recommendation = self.recommend_opportunity(refresh_if_due=False)
        return self._response(
            "STRATEGIC_DEVELOPMENT_CYCLE_COMPLETED",
            success=True,
            selected=selected.get("selected", {}),
            recommendation=recommendation.get("recommendation", {}),
            refresh=refreshed,
        )

    def start_background(self) -> dict[str, Any]:
        if self.is_running():
            return self._response(
                "STRATEGIC_DEVELOPMENT_SUPERVISOR_ALREADY_RUNNING",
                success=True,
            )
        with self._lock:
            if self.is_running():
                return self._response(
                    "STRATEGIC_DEVELOPMENT_SUPERVISOR_ALREADY_RUNNING",
                    success=True,
                )
            policy = self.store.update_policy({"auto_approve": False})
            self.store.update_runtime({
                "enabled": True,
                "paused": False,
                "running": False,
                "phase": "STARTING",
                "last_error": "",
            })
            if bool(policy.get("start_b56_with_supervisor", True)):
                self.self_directed.start_background()
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
                name="jarvis-strategic-development",
                daemon=True,
            )
            self._thread.start()
            return self._response(
                "STRATEGIC_DEVELOPMENT_SUPERVISOR_STARTED",
                success=True,
            )

    def start_if_enabled(self) -> dict[str, Any]:
        self.store.compact()
        if bool(self.store.runtime().get("enabled", False)):
            return self.start_background()
        return self._response(
            "STRATEGIC_DEVELOPMENT_SUPERVISOR_DISABLED",
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
        self.self_directed.stop_background()
        runtime = self.store.update_runtime({
            "enabled": False,
            "paused": False,
            "running": False,
            "phase": "STOPPED",
        })
        return self._response(
            "STRATEGIC_DEVELOPMENT_SUPERVISOR_STOPPED",
            success=True,
            runtime=runtime,
        )

    def pause(self) -> dict[str, Any]:
        self.self_directed.pause()
        runtime = self.store.update_runtime({
            "paused": True,
            "phase": "PAUSED",
        })
        return self._response(
            "STRATEGIC_DEVELOPMENT_SUPERVISOR_PAUSED",
            success=True,
            runtime=runtime,
        )

    def resume(self) -> dict[str, Any]:
        self.self_directed.resume()
        runtime = self.store.update_runtime({
            "enabled": True,
            "paused": False,
            "phase": "RESUMED",
        })
        if not self.is_running():
            return self.start_background()
        return self._response(
            "STRATEGIC_DEVELOPMENT_SUPERVISOR_RESUMED",
            success=True,
            runtime=runtime,
        )

    def status(self) -> dict[str, Any]:
        runtime = self.store.runtime()
        active_goal = self.store.get_goal(
            str(runtime.get("active_goal_id", ""))
        )
        return self._response(
            "STRATEGIC_DEVELOPMENT_STATUS",
            success=True,
            selected=active_goal or {},
            goals=self.store.list_goals(limit=20),
        )

    def roadmap(self, *, limit: int = 50) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_DEVELOPMENT_ROADMAP",
            success=True,
            goals=self.store.list_goals(limit=limit),
        )

    def history(self, *, limit: int = 20) -> dict[str, Any]:
        return self._response(
            "STRATEGIC_DEVELOPMENT_HISTORY",
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
            "STRATEGIC_DEVELOPMENT_POLICY_UPDATED",
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
            and policy.get("integrate_with_b56", True)
        )

    def _run_loop(self) -> None:
        try:
            if self._stop_event.wait(24.0):
                return

            while not self._stop_event.is_set():
                try:
                    if not bool(self.store.runtime().get("paused", False)):
                        self.run_cycle()
                except Exception as error:
                    self.store.update_runtime({
                        "last_error": f"{type(error).__name__}: {error}",
                        "phase": "FAILED",
                    })
                interval = float(
                    self.store.policy().get(
                        "refresh_interval_seconds",
                        300.0,
                    )
                )
                self._stop_event.wait(max(60.0, interval))
        finally:
            self.store.update_runtime({"running": False})

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
            "operation": "strategic_development",
            "runtime": dict(extra.pop("runtime", self.store.runtime())),
            "policy": dict(extra.pop("policy", self.store.policy())),
            "summary": self.store.summary(),
            "project_summary": self.project_intelligence.store.summary(),
            "errors": list(errors or []),
            "report_path": str(self.store.path),
            **extra,
        }

    def _record(self, response: dict[str, Any]) -> None:
        selected = response.get("selected", {})
        recommendation = response.get("recommendation", {})
        errors = response.get("errors", [])
        self.store.record_history({
            "status": response.get("status", "UNKNOWN"),
            "success": bool(response.get("success", False)),
            "phase": self.store.runtime().get("phase", ""),
            "goal_id": (
                selected.get("goal_id", "")
                if isinstance(selected, dict)
                else ""
            ),
            "opportunity_id": (
                recommendation.get("opportunity_id", "")
                if isinstance(recommendation, dict)
                else ""
            ),
            "error": "; ".join(str(item) for item in errors[:5])
            if isinstance(errors, list)
            else "",
        })

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
    def _result_summary(response: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": str(response.get("status", "UNKNOWN")),
            "success": bool(response.get("success", False)),
        }

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

    def _refresh_due(
        self,
        runtime: dict[str, Any],
        policy: dict[str, Any],
    ) -> bool:
        last_refresh = self._parse_time(runtime.get("last_refresh_at", ""))
        if last_refresh is None:
            return True
        elapsed = (
            datetime.now(timezone.utc) - last_refresh
        ).total_seconds()
        return elapsed >= float(
            policy.get("refresh_interval_seconds", 300.0)
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


def bootstrap_strategic_development(
    controller: Any,
) -> StrategicDevelopmentService:
    service = getattr(controller, "strategic_development_service", None)
    if service is None:
        project_intelligence = bootstrap_project_intelligence(controller)
        self_directed = bootstrap_self_directed_development(controller)
        service = StrategicDevelopmentService(
            controller.project_root,
            project_intelligence=project_intelligence,
            self_directed=self_directed,
        )
        controller.strategic_development_service = service
        project_intelligence.strategic_development_service = service
        self_directed.strategic_development_service = service
    service.start_if_enabled()
    return service
