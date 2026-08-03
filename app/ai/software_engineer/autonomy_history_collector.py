from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from .change_campaign_store import ChangeCampaignStore
from .full_autonomy_store import FullAutonomyStore
from .multi_campaign_store import MultiCampaignStore
from .portfolio_director_store import PortfolioDirectorStore


class AutonomyHistoryCollector:
    """Normalizes autonomy, portfolio and campaign history into episodes."""

    TERMINAL_RUN_MARKERS = (
        "COMPLETED",
        "FAILED",
        "ROLLED_BACK",
        "CANCELLED",
    )
    TERMINAL_CAMPAIGN_MARKERS = (
        "COMPLETED",
        "FAILED",
        "ROLLED_BACK",
        "BLOCKED",
        "CANCELLED",
    )

    def __init__(
        self,
        project_root: str | Path,
        *,
        full_store: FullAutonomyStore | Any | None = None,
        portfolio_store: MultiCampaignStore | Any | None = None,
        campaign_store: ChangeCampaignStore | Any | None = None,
        director_store: PortfolioDirectorStore | Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(strict=False)
        self.full_store = full_store or FullAutonomyStore(self.project_root)
        self.portfolio_store = portfolio_store or MultiCampaignStore(self.project_root)
        self.campaign_store = campaign_store or ChangeCampaignStore(self.project_root)
        self.director_store = director_store or PortfolioDirectorStore(self.project_root)

    def collect(
        self,
        *,
        limit: int = 500,
    ) -> dict[str, Any]:
        safe_limit = min(5000, max(1, int(limit)))
        episodes: list[dict[str, Any]] = []
        source_counts = {
            "full_autonomy": 0,
            "portfolio_campaign": 0,
            "change_campaign": 0,
        }

        for run in self._safe_list(self.full_store, safe_limit):
            episode = self.from_full_run(run)
            if episode is not None:
                episodes.append(episode)
                source_counts["full_autonomy"] += 1

        for portfolio in self._safe_list(self.portfolio_store, safe_limit):
            for campaign in self._as_list(portfolio.get("campaigns", [])):
                episode = self.from_portfolio_campaign(
                    portfolio,
                    campaign,
                )
                if episode is not None:
                    episodes.append(episode)
                    source_counts["portfolio_campaign"] += 1

        for campaign in self._safe_list(self.campaign_store, safe_limit):
            episode = self.from_change_campaign(campaign)
            if episode is not None:
                episodes.append(episode)
                source_counts["change_campaign"] += 1

        deduplicated: dict[str, dict[str, Any]] = {}
        for episode in episodes:
            deduplicated[str(episode["episode_id"])] = episode

        values = sorted(
            deduplicated.values(),
            key=lambda item: str(
                item.get("completed_at")
                or item.get("started_at")
                or item.get("created_at")
                or ""
            ),
        )
        return {
            "success": True,
            "status": "AUTONOMY_HISTORY_COLLECTED",
            "episodes": values[-safe_limit:],
            "episodes_count": min(len(values), safe_limit),
            "source_counts": source_counts,
        }

    def from_full_run(
        self,
        run: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(run, dict):
            return None
        status = str(run.get("status", "")).upper()
        if not self._terminal(status, self.TERMINAL_RUN_MARKERS):
            return None

        plan = self._as_dict(run.get("plan"))
        execution = self._as_dict(run.get("execution"))
        director_result = self._as_dict(run.get("director_result"))
        director_run = self._as_dict(director_result.get("director_run"))
        final_report = self._as_dict(run.get("final_report"))
        rollback = self._as_dict(run.get("rollback"))
        source_id = str(run.get("run_id", "")).strip()
        if not source_id:
            return None

        successes = status == "FULL_AUTONOMY_COMPLETED" and bool(
            run.get("success", False)
        )
        rolled_back = (
            "ROLLBACK" in status
            or "ROLLED_BACK" in status
            or bool(rollback.get("success", False))
        )
        retries = self._integer(
            director_run.get(
                "retries",
                final_report.get("director_retries", 0),
            )
        )
        failures = self._integer(
            director_run.get(
                "failures",
                final_report.get("director_failures", 0),
            )
        )
        terminal_failure = (
            not successes
            and any(
                marker in status
                for marker in ("FAILED", "BLOCKED", "CANCELLED")
            )
        )
        if terminal_failure:
            failures = max(1, failures)
        targets = self._strings(plan.get("target_files", []))
        subsystems = self._strings(plan.get("subsystems", []))
        changed_files = self._strings(execution.get("changed_files", []))
        campaign_count = len(self._as_list(plan.get("campaigns", [])))
        stage_count = self._integer(
            execution.get("stages_total", 0)
        )

        return self._episode(
            episode_type="full_autonomy",
            source="full_autonomy_runs",
            source_id=source_id,
            objective=str(run.get("objective", "")),
            status=status,
            success=successes,
            rolled_back=rolled_back,
            retry_count=retries,
            failure_count=failures,
            started_at=str(run.get("started_at", "")),
            completed_at=str(run.get("completed_at", "")),
            estimated_roi=self._score(
                plan.get("estimated_roi"),
                maximum=10.0,
            ),
            estimated_risk=self._score(
                plan.get("estimated_risk"),
                maximum=10.0,
            ),
            estimated_minutes=self._number(
                plan.get("estimated_minutes", 0.0)
            ),
            confidence=self._confidence(plan.get("confidence")),
            subsystems=subsystems,
            targets=targets,
            campaign_count=campaign_count,
            stage_count=stage_count,
            changed_files_count=len(changed_files),
            errors=self._strings(run.get("errors", [])),
            metadata={
                "goal_id": str(run.get("goal_id", "")),
                "portfolio_id": str(run.get("portfolio_id", "")),
                "director_run_id": str(run.get("director_run_id", "")),
                "final_validation_success": bool(
                    self._as_dict(run.get("final_validation")).get(
                        "success",
                        False,
                    )
                ),
                "progress_percent": self._number(
                    execution.get("progress_percent", 0.0)
                ),
            },
        )

    def from_portfolio_campaign(
        self,
        portfolio: dict[str, Any],
        campaign: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(campaign, dict):
            return None
        status = str(campaign.get("status", "")).upper()
        if not self._terminal(status, self.TERMINAL_CAMPAIGN_MARKERS):
            return None

        source_id = str(campaign.get("campaign_id", "")).strip()
        portfolio_id = str(portfolio.get("portfolio_id", "")).strip()
        if not source_id:
            return None

        metadata = self._as_dict(campaign.get("metadata"))
        result = self._as_dict(campaign.get("result"))
        combined = f"{status} {str(result.get('status', '')).upper()}"
        targets = self._strings(campaign.get("targets", []))
        subsystems = self._strings(
            metadata.get(
                "subsystems",
                portfolio.get("metadata", {}).get("subsystems", [])
                if isinstance(portfolio.get("metadata"), dict)
                else [],
            )
        )
        stages = self._as_list(campaign.get("stages", []))
        retries = self._integer(
            result.get(
                "attempts",
                metadata.get("retry_count", 0),
            )
        )
        success = "COMPLETED" in combined and "ROLLBACK" not in combined
        rolled_back = "ROLLBACK" in combined or status == "ROLLED_BACK"

        return self._episode(
            episode_type="portfolio_campaign",
            source="multi_campaign_portfolios",
            source_id=f"{portfolio_id}:{source_id}",
            objective=str(campaign.get("objective", "")),
            status=status,
            success=success,
            rolled_back=rolled_back,
            retry_count=max(0, retries - 1),
            failure_count=1 if any(
                marker in combined
                for marker in ("FAILED", "BLOCKED", "CANCELLED")
            ) else 0,
            started_at=str(
                campaign.get("started_at")
                or portfolio.get("started_at")
                or ""
            ),
            completed_at=str(
                campaign.get("completed_at")
                or portfolio.get("completed_at")
                or ""
            ),
            estimated_roi=self._score(
                metadata.get(
                    "estimated_roi",
                    metadata.get("roi"),
                ),
                maximum=10.0,
            ),
            estimated_risk=self._score(
                metadata.get(
                    "estimated_risk",
                    metadata.get("risk"),
                ),
                maximum=10.0,
            ),
            estimated_minutes=self._number(
                metadata.get(
                    "estimated_minutes",
                    max(1, len(stages)) * 20,
                )
            ),
            confidence=self._confidence(metadata.get("confidence")),
            subsystems=subsystems,
            targets=targets,
            campaign_count=1,
            stage_count=len(stages),
            changed_files_count=len(
                self._strings(
                    result.get(
                        "changed_files",
                        metadata.get("changed_files", []),
                    )
                )
            ),
            errors=self._strings(
                result.get("errors", campaign.get("errors", []))
            ),
            metadata={
                "portfolio_id": portfolio_id,
                "campaign_id": source_id,
                "priority": str(campaign.get("priority", "")),
                "priority_score": self._number(
                    campaign.get("priority_score", 0)
                ),
            },
        )

    def from_change_campaign(
        self,
        campaign: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not isinstance(campaign, dict):
            return None
        status = str(campaign.get("status", "")).upper()
        if not self._terminal(status, self.TERMINAL_CAMPAIGN_MARKERS):
            return None
        source_id = str(campaign.get("campaign_id", "")).strip()
        if not source_id:
            return None

        metadata = self._as_dict(campaign.get("metadata"))
        stages = self._as_list(campaign.get("stages", []))
        attempts = sum(
            self._integer(self._as_dict(stage).get("attempts", 0))
            for stage in stages
        )
        stage_failures = sum(
            1
            for stage in stages
            if any(
                marker in str(self._as_dict(stage).get("status", "")).upper()
                for marker in ("FAILED", "BLOCKED", "CANCELLED")
            )
        )
        success = "COMPLETED" in status and "ROLLBACK" not in status
        rolled_back = "ROLLBACK" in status or status == "ROLLED_BACK"

        return self._episode(
            episode_type="change_campaign",
            source="change_campaigns",
            source_id=source_id,
            objective=str(campaign.get("objective", "")),
            status=status,
            success=success,
            rolled_back=rolled_back,
            retry_count=max(0, attempts - len(stages)),
            failure_count=stage_failures,
            started_at=str(campaign.get("started_at", "")),
            completed_at=str(campaign.get("completed_at", "")),
            estimated_roi=self._score(
                metadata.get("estimated_roi"),
                maximum=10.0,
            ),
            estimated_risk=self._score(
                metadata.get("estimated_risk"),
                maximum=10.0,
            ),
            estimated_minutes=self._number(
                metadata.get("estimated_minutes", max(1, len(stages)) * 20)
            ),
            confidence=self._confidence(metadata.get("confidence")),
            subsystems=self._strings(metadata.get("subsystems", [])),
            targets=self._strings(campaign.get("target_files", [])),
            campaign_count=1,
            stage_count=len(stages),
            changed_files_count=len(
                self._strings(campaign.get("changed_files", []))
            ),
            errors=self._strings(campaign.get("errors", [])),
            metadata={
                "campaign_id": source_id,
                "portfolio_id": str(metadata.get("portfolio_id", "")),
            },
        )

    def _episode(
        self,
        *,
        episode_type: str,
        source: str,
        source_id: str,
        objective: str,
        status: str,
        success: bool,
        rolled_back: bool,
        retry_count: int,
        failure_count: int,
        started_at: str,
        completed_at: str,
        estimated_roi: float,
        estimated_risk: float,
        estimated_minutes: float,
        confidence: float,
        subsystems: list[str],
        targets: list[str],
        campaign_count: int,
        stage_count: int,
        changed_files_count: int,
        errors: list[str],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        duration_seconds = self._duration_seconds(started_at, completed_at)
        signature = self._signature(objective, targets, subsystems)
        episode_id = sha256(
            f"{source}|{source_id}".encode("utf-8")
        ).hexdigest()
        return {
            "episode_id": episode_id,
            "episode_type": episode_type,
            "source": source,
            "source_id": source_id,
            "objective": " ".join(str(objective).split()),
            "signature": signature,
            "status": status,
            "success": bool(success),
            "rolled_back": bool(rolled_back),
            "retry_count": max(0, int(retry_count)),
            "failure_count": max(0, int(failure_count)),
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": round(duration_seconds, 3),
            "actual_minutes": round(duration_seconds / 60.0, 3),
            "estimated_roi": round(estimated_roi, 3),
            "estimated_risk": round(estimated_risk, 3),
            "estimated_minutes": round(max(0.0, estimated_minutes), 3),
            "confidence": round(confidence, 4),
            "subsystems": list(dict.fromkeys(subsystems)),
            "targets": list(dict.fromkeys(targets)),
            "target_count": len(set(targets)),
            "campaign_count": max(0, int(campaign_count)),
            "stage_count": max(0, int(stage_count)),
            "changed_files_count": max(0, int(changed_files_count)),
            "errors": errors[:50],
            "metadata": dict(metadata),
        }

    @staticmethod
    def _terminal(status: str, markers: Iterable[str]) -> bool:
        return any(marker in status for marker in markers)

    @staticmethod
    def _safe_list(store: Any, limit: int) -> list[dict[str, Any]]:
        try:
            values = store.list_recent(limit=limit)
        except Exception:
            return []
        return [
            dict(item)
            for item in values
            if isinstance(item, dict)
        ]

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        return list(value) if isinstance(value, (list, tuple)) else []

    @staticmethod
    def _strings(value: Any) -> list[str]:
        if isinstance(value, (str, bytes)):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            return []
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _score(
        cls,
        value: Any,
        *,
        maximum: float,
    ) -> float:
        number = cls._number(value)
        if 0.0 <= number <= 1.0 and maximum > 1.0:
            number *= maximum
        return max(0.0, min(maximum, number))

    @classmethod
    def _confidence(cls, value: Any) -> float:
        return max(0.0, min(1.0, cls._number(value)))

    @staticmethod
    def _duration_seconds(started_at: str, completed_at: str) -> float:
        if not started_at or not completed_at:
            return 0.0
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            return max(0.0, (end - start).total_seconds())
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _signature(
        objective: str,
        targets: list[str],
        subsystems: list[str],
    ) -> str:
        normalized_objective = " ".join(str(objective).casefold().split())
        normalized_targets = "|".join(
            sorted(
                str(item).replace("\\", "/").casefold()
                for item in targets
            )
        )
        normalized_subsystems = "|".join(
            sorted(str(item).casefold() for item in subsystems)
        )
        return sha256(
            f"{normalized_objective}|{normalized_targets}|{normalized_subsystems}".encode(
                "utf-8"
            )
        ).hexdigest()
