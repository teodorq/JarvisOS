from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FullAutonomyExecutionTracker:
    """Builds persistent, bounded progress snapshots for full autonomy."""

    TERMINAL_CAMPAIGNS = {
        "COMPLETED",
        "FAILED",
        "ROLLED_BACK",
        "BLOCKED",
        "CANCELLED",
    }
    TERMINAL_STAGES = {
        "COMPLETED",
        "FAILED",
        "ROLLED_BACK",
        "PREVIEW_READY",
        "CANCELLED",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        portfolio_workflow: Any,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(
            strict=False
        )
        self.portfolio_workflow = portfolio_workflow

    def snapshot(
        self,
        run: dict[str, Any],
        *,
        event: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        portfolio_id = str(
            run.get("portfolio_id", "")
        ).strip()
        portfolio = self._portfolio(
            portfolio_id
        )
        campaigns = [
            dict(item)
            for item in portfolio.get(
                "campaigns",
                [],
            )
            if isinstance(item, dict)
        ]
        campaign_details = [
            self._campaign_detail(item)
            for item in campaigns
        ]
        stage_total = sum(
            len(item.get("stages", []))
            for item in campaign_details
        )
        stage_completed = sum(
            1
            for item in campaign_details
            for stage in item.get("stages", [])
            if str(
                stage.get("status", "")
            ).upper() == "COMPLETED"
        )
        campaign_completed = sum(
            str(item.get("status", "")).upper()
            == "COMPLETED"
            for item in campaigns
        )
        campaign_failed = sum(
            str(item.get("status", "")).upper()
            in {
                "FAILED",
                "BLOCKED",
                "ROLLED_BACK",
            }
            for item in campaigns
        )
        campaign_total = len(campaigns)
        current_campaign_id = str(
            portfolio.get(
                "current_campaign_id",
                "",
            )
        )
        current_stage_id = ""
        current_campaign = next(
            (
                item
                for item in campaign_details
                if str(
                    item.get("campaign_id", "")
                ) == current_campaign_id
            ),
            {},
        )
        if current_campaign:
            current_stage_id = str(
                current_campaign.get(
                    "current_stage_id",
                    "",
                )
            )

        denominator = (
            stage_total
            if stage_total > 0
            else campaign_total
        )
        numerator = (
            stage_completed
            if stage_total > 0
            else campaign_completed
        )
        percent = round(
            100.0 * numerator / denominator,
            2,
        ) if denominator else 0.0

        if str(
            run.get("status", "")
        ).upper() == "FULL_AUTONOMY_COMPLETED":
            percent = 100.0

        changed_files = self._changed_files(
            run,
            portfolio,
            campaign_details,
        )
        checkpoint = {
            "timestamp": self._now(),
            "event": str(event),
            "run_status": str(
                run.get("status", "")
            ),
            "portfolio_status": str(
                portfolio.get("status", "")
            ),
            "campaigns_total": campaign_total,
            "campaigns_completed": campaign_completed,
            "campaigns_failed": campaign_failed,
            "stages_total": stage_total,
            "stages_completed": stage_completed,
            "current_campaign_id": current_campaign_id,
            "current_stage_id": current_stage_id,
            "progress_percent": percent,
            "changed_files_count": len(changed_files),
            "metadata": dict(metadata or {}),
        }
        previous = dict(
            run.get("execution", {})
            or {}
        )
        history = [
            dict(item)
            for item in previous.get(
                "checkpoints",
                [],
            )
            if isinstance(item, dict)
        ]
        if event:
            history.append(checkpoint)
        if len(history) > 300:
            history = history[-300:]

        return {
            "status": self._execution_status(
                run,
                portfolio,
            ),
            "phase": self._phase(
                run,
                portfolio,
            ),
            "progress_percent": percent,
            "campaigns_total": campaign_total,
            "campaigns_completed": campaign_completed,
            "campaigns_failed": campaign_failed,
            "campaigns_pending": max(
                0,
                campaign_total
                - campaign_completed
                - campaign_failed,
            ),
            "stages_total": stage_total,
            "stages_completed": stage_completed,
            "current_campaign_id": current_campaign_id,
            "current_stage_id": current_stage_id,
            "changed_files": changed_files,
            "started_at": str(
                previous.get(
                    "started_at",
                    run.get("started_at", ""),
                )
            ),
            "updated_at": self._now(),
            "last_checkpoint": checkpoint,
            "checkpoints": history,
        }

    def _portfolio(
        self,
        portfolio_id: str,
    ) -> dict[str, Any]:
        if not portfolio_id:
            return {}

        getter = getattr(
            self.portfolio_workflow,
            "get_portfolio",
            None,
        )

        if callable(getter):
            try:
                value = getter(portfolio_id)
            except Exception:
                value = None

            if isinstance(value, dict):
                return dict(value)

        store = getattr(
            self.portfolio_workflow,
            "store",
            None,
        )
        getter = getattr(store, "get", None)

        if callable(getter):
            try:
                value = getter(portfolio_id)
            except Exception:
                value = None

            if hasattr(value, "to_dict"):
                value = value.to_dict()

            if isinstance(value, dict):
                return dict(value)

        return {}

    def _campaign_detail(
        self,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        campaign_id = str(
            summary.get(
                "campaign_id",
                "",
            )
        )
        campaign_workflow = getattr(
            self.portfolio_workflow,
            "campaign_workflow",
            None,
        )
        getter = getattr(
            campaign_workflow,
            "get_campaign",
            None,
        )

        if callable(getter) and campaign_id:
            try:
                value = getter(campaign_id)
            except Exception:
                value = None

            if isinstance(value, dict):
                return dict(value)

        return dict(summary)

    @staticmethod
    def _execution_status(
        run: dict[str, Any],
        portfolio: dict[str, Any],
    ) -> str:
        run_status = str(
            run.get("status", "")
        ).upper()
        portfolio_status = str(
            portfolio.get("status", "")
        ).upper()

        if run_status.startswith(
            "FULL_AUTONOMY_FINAL_VALIDATION"
        ):
            return "VALIDATING"
        if run_status == "FULL_AUTONOMY_COMPLETED":
            return "COMPLETED"
        if "ROLLED_BACK" in run_status:
            return "ROLLED_BACK"
        if "FAILED" in run_status:
            return "FAILED"
        if "PAUSED" in run_status or "PAUSED" in portfolio_status:
            return "PAUSED"
        if run_status == "FULL_AUTONOMY_PLAN_READY":
            return "PLAN_READY"
        if "RUNNING" in run_status or "RUNNING" in portfolio_status:
            return "RUNNING"
        return run_status or portfolio_status or "UNKNOWN"

    @staticmethod
    def _phase(
        run: dict[str, Any],
        portfolio: dict[str, Any],
    ) -> str:
        status = str(
            run.get("status", "")
        ).upper()

        if "PLANNING" in status or status.endswith(
            "STARTING"
        ):
            return "PLANNING"
        if "PLAN_READY" in status:
            return "PLAN_READY"
        if "VALIDATION" in status:
            return "FINAL_VALIDATION"
        if "ROLLBACK" in status:
            return "ROLLBACK"
        if "COMPLETED" in status:
            return "COMPLETED"
        if "FAILED" in status:
            return "FAILED"
        if "PAUSED" in status:
            return "PAUSED"

        if portfolio.get(
            "current_campaign_id"
        ):
            return "CAMPAIGN_EXECUTION"

        return "PORTFOLIO_EXECUTION"

    def _changed_files(
        self,
        run: dict[str, Any],
        portfolio: dict[str, Any],
        campaigns: list[dict[str, Any]],
    ) -> list[str]:
        plan = dict(
            run.get("plan", {})
            or {}
        )
        planned = [
            str(path).replace("\\", "/")
            for path in plan.get(
                "target_files",
                [],
            )
            if str(path).strip()
        ]
        discovered: list[str] = []

        for campaign in campaigns:
            campaign_status = str(
                campaign.get("status", "")
            ).upper()

            if not self._rolled_back_or_failed(
                campaign_status
            ):
                self._collect_paths(
                    campaign.get(
                        "result",
                        {},
                    ),
                    discovered,
                )

            for stage in campaign.get(
                "stages",
                [],
            ):
                if not isinstance(stage, dict):
                    continue

                stage_status = str(
                    stage.get("status", "")
                ).upper()

                if (
                    stage_status == "COMPLETED"
                    and not self._rolled_back_or_failed(
                        stage_status
                    )
                ):
                    self._collect_paths(
                        stage.get(
                            "result",
                            {},
                        ),
                        discovered,
                    )

        candidates = list(discovered)

        if (
            not candidates
            and str(
                run.get("status", "")
            ).upper()
            == "FULL_AUTONOMY_COMPLETED"
        ):
            candidates = list(planned)

        normalized = [
            relative
            for relative in (
                self._safe_relative(path)
                for path in candidates
            )
            if relative
        ]
        result = list(
            dict.fromkeys(normalized)
        )
        planned_set = set(planned)

        return sorted(
            result,
            key=lambda path: (
                path not in planned_set,
                path,
            ),
        )

    @staticmethod
    def _rolled_back_or_failed(
        status: str,
    ) -> bool:
        normalized = str(status).upper()
        return any(
            token in normalized
            for token in (
                "FAILED",
                "ROLLED_BACK",
                "CANCELLED",
                "BLOCKED",
            )
        )

    def _collect_paths(
        self,
        value: Any,
        output: list[str],
        *,
        depth: int = 0,
    ) -> None:
        if depth > 8:
            return

        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = str(
                    key
                ).casefold()

                if normalized_key in {
                    "changed_files",
                    "created_files",
                    "updated_files",
                    "removed_files",
                    "files",
                    "targets",
                    "target_files",
                }:
                    self._append_paths(
                        item,
                        output,
                    )
                else:
                    self._collect_paths(
                        item,
                        output,
                        depth=depth + 1,
                    )

        elif isinstance(value, list):
            for item in value:
                self._collect_paths(
                    item,
                    output,
                    depth=depth + 1,
                )

    @staticmethod
    def _append_paths(
        value: Any,
        output: list[str],
    ) -> None:
        values = (
            value
            if isinstance(
                value,
                (list, tuple, set),
            )
            else [value]
        )

        for item in values:
            if isinstance(item, dict):
                candidate = item.get(
                    "relative_path",
                    item.get(
                        "path",
                        "",
                    ),
                )
            else:
                candidate = item

            text = str(
                candidate
            ).strip().replace(
                "\\",
                "/",
            )

            if text.endswith(".py"):
                output.append(text)

    def _safe_relative(
        self,
        value: str,
    ) -> str:
        text = str(value).strip().replace(
            "\\",
            "/",
        )

        if not text.endswith(".py"):
            return ""

        candidate = Path(text).expanduser()

        if not candidate.is_absolute():
            candidate = self.project_root / candidate

        try:
            relative = candidate.resolve(
                strict=False
            ).relative_to(
                self.project_root
            )
        except ValueError:
            return ""

        return relative.as_posix()

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()
