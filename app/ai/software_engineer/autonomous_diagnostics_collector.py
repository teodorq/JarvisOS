from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .change_campaign_store import ChangeCampaignStore
from .full_autonomy_store import FullAutonomyStore
from .long_running_autonomy_store import LongRunningAutonomyStore
from .multi_campaign_store import MultiCampaignStore
from .portfolio_director_store import PortfolioDirectorStore


class AutonomousDiagnosticsCollector:
    """Collects one bounded evidence graph across autonomy layers."""

    _SECRET_PATTERNS = (
        re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
        re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
    )
    _NON_EXECUTION_EVIDENCE_KEYS = {
        "learning_observation",
        "learning_advice",
        "training_advice",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        long_running_store: LongRunningAutonomyStore | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.long_running_store = long_running_store or LongRunningAutonomyStore(
            self.project_root
        )
        self.full_store = FullAutonomyStore(self.project_root)
        self.portfolio_store = MultiCampaignStore(self.project_root)
        self.director_store = PortfolioDirectorStore(self.project_root)
        self.campaign_store = ChangeCampaignStore(self.project_root)

    def collect_job(
        self,
        job_id: str,
        *,
        response: dict[str, Any] | None = None,
        exception: BaseException | None = None,
        traceback_text: str = "",
    ) -> dict[str, Any]:
        job = self.long_running_store.get_job(job_id) or {}
        run_id = str(
            (response or {}).get(
                "autonomy_run_id",
                job.get("autonomy_run_id", ""),
            )
        ).strip()
        run = self.full_store.get(run_id) if run_id else None
        run = dict(run or {})
        portfolio_id = str(
            run.get(
                "portfolio_id",
                (response or {}).get("portfolio_id", ""),
            )
        ).strip()
        portfolio_object = (
            self.portfolio_store.get(portfolio_id)
            if portfolio_id
            else None
        )
        portfolio = (
            portfolio_object.to_dict()
            if portfolio_object is not None
            else dict(run.get("portfolio", {}) or {})
        )
        director_run_id = str(
            run.get(
                "director_run_id",
                (response or {}).get("director_run_id", ""),
            )
        ).strip()
        director = self.director_store.get(director_run_id) \
            if director_run_id else None
        director = dict(director or run.get("director_result", {}) or {})

        campaigns: list[dict[str, Any]] = []
        for item in portfolio.get("campaigns", []) \
                if isinstance(portfolio, dict) else []:
            if not isinstance(item, dict):
                continue
            campaign_id = str(item.get("campaign_id", "")).strip()
            stored = self.campaign_store.get(campaign_id) if campaign_id else None
            campaigns.append(
                stored.to_dict() if stored is not None else dict(item)
            )

        snapshot = {
            "job": dict(job),
            "response": dict(response or {}),
            "run": run,
            "portfolio": portfolio,
            "director": director,
            "campaigns": campaigns,
            "exception": {
                "type": type(exception).__name__ if exception else "",
                "message": str(exception) if exception else "",
                "traceback": str(traceback_text),
            },
            "identifiers": {
                "job_id": str(job_id),
                "autonomy_run_id": run_id,
                "portfolio_id": portfolio_id,
                "director_run_id": director_run_id,
            },
        }
        return self._redact(self._bounded(snapshot, depth=0))

    def collect_run(
        self,
        run_id: str,
        *,
        response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        job_id = ""
        for job in self.long_running_store.list_jobs(limit=1000):
            if str(job.get("autonomy_run_id", "")) == str(run_id):
                job_id = str(job.get("job_id", ""))
                break
        if job_id:
            return self.collect_job(job_id, response=response)
        run = self.full_store.get(run_id) or {}
        pseudo_job = {
            "job_id": "",
            "autonomy_run_id": run_id,
            "last_result": dict(response or {}),
        }
        snapshot = self.collect_job("", response={
            **dict(response or {}),
            "autonomy_run_id": run_id,
        })
        snapshot["job"] = pseudo_job
        return snapshot

    def evidence(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        statuses: list[str] = []
        errors: list[str] = []
        tracebacks: list[str] = []
        stdouts: list[str] = []
        stderrs: list[str] = []
        files: list[str] = []
        current_stage = ""
        current_campaign = ""

        def walk(value: Any, *, key: str = "", depth: int = 0) -> None:
            nonlocal current_stage, current_campaign
            if depth > 10:
                return
            if isinstance(value, dict):
                for child_key, child in value.items():
                    normalized_key = str(child_key).casefold()
                    if normalized_key in self._NON_EXECUTION_EVIDENCE_KEYS:
                        continue
                    if normalized_key in {"status", "state"}:
                        text = str(child).strip().upper()
                        if text and text not in statuses:
                            statuses.append(text)
                    elif normalized_key in {
                        "error", "errors", "reason", "reasons", "message"
                    }:
                        self._collect_text(child, errors)
                    elif "traceback" in normalized_key:
                        self._collect_text(child, tracebacks)
                    elif normalized_key == "stdout":
                        self._collect_text(child, stdouts)
                    elif normalized_key == "stderr":
                        self._collect_text(child, stderrs)
                    elif normalized_key in {
                        "path", "target", "target_path", "relative_path"
                    }:
                        text = str(child).strip()
                        if text and text not in files:
                            files.append(text)
                    elif normalized_key in {
                        "files", "targets", "changed_files", "rollback_scope"
                    }:
                        self._collect_files(child, files)
                    elif normalized_key == "current_stage_id" and child:
                        current_stage = str(child)
                    elif normalized_key == "current_campaign_id" and child:
                        current_campaign = str(child)
                    walk(child, key=normalized_key, depth=depth + 1)
            elif isinstance(value, list):
                for child in value:
                    walk(child, key=key, depth=depth + 1)

        walk(snapshot)
        exception = snapshot.get("exception", {})
        if isinstance(exception, dict):
            if exception.get("message"):
                errors.append(
                    f"{exception.get('type', 'Exception')}: "
                    f"{exception.get('message')}"
                )
            if exception.get("traceback"):
                tracebacks.append(str(exception.get("traceback")))

        return {
            "statuses": statuses[:100],
            "errors": self._unique(errors)[:50],
            "traceback": "\n\n".join(self._unique(tracebacks))[:12000],
            "stdout": "\n".join(self._unique(stdouts))[:12000],
            "stderr": "\n".join(self._unique(stderrs))[:12000],
            "files": self._unique(files)[:100],
            "current_stage_id": current_stage,
            "current_campaign_id": current_campaign,
        }

    @staticmethod
    def _collect_text(value: Any, target: list[str]) -> None:
        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text:
                    target.append(text)
        elif isinstance(value, dict):
            for item in value.values():
                AutonomousDiagnosticsCollector._collect_text(item, target)
        else:
            text = str(value).strip()
            if text:
                target.append(text)

    @staticmethod
    def _collect_files(value: Any, target: list[str]) -> None:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    candidate = item.get("relative_path", item.get("path", ""))
                else:
                    candidate = item
                text = str(candidate).strip()
                if text and text not in target:
                    target.append(text)
        elif isinstance(value, dict):
            for key in value:
                text = str(key).strip()
                if text and text not in target:
                    target.append(text)

    def _redact(self, value: Any) -> Any:
        root = str(self.project_root)
        if isinstance(value, dict):
            return {str(key): self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            text = value.replace(root, "<PROJECT_ROOT>")
            for pattern in self._SECRET_PATTERNS:
                text = pattern.sub("<REDACTED>", text)
            return text
        return value

    @classmethod
    def _bounded(cls, value: Any, *, depth: int) -> Any:
        if depth > 8:
            return "<depth-limit>"
        if isinstance(value, dict):
            return {
                str(key)[:120]: cls._bounded(item, depth=depth + 1)
                for key, item in list(value.items())[:150]
            }
        if isinstance(value, list):
            return [cls._bounded(item, depth=depth + 1) for item in value[:200]]
        if isinstance(value, str):
            return value[:16000]
        if isinstance(value, (bool, int, float)) or value is None:
            return value
        return str(value)[:2000]

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        result: list[str] = []
        for item in values:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result
