from __future__ import annotations

from typing import Any

from .project_intelligence_models import (
    ACTIVE_OPPORTUNITY_STATES,
    TERMINAL_OPPORTUNITY_STATES,
)


class ProjectOpportunityRanker:
    """Deterministic ROI/risk ranking for B55 opportunities."""

    SEVERITY_VALUE = {
        "CRITICAL": 40.0,
        "HIGH": 30.0,
        "MEDIUM": 20.0,
        "LOW": 10.0,
    }

    def score(
        self,
        opportunity: dict[str, Any],
        *,
        completed_fingerprints: set[str] | None = None,
        failed_fingerprints: set[str] | None = None,
        failed_issue_type_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        item = dict(opportunity)
        severity = str(item.get("severity", "MEDIUM")).upper()
        value = float(
            item.get(
                "value_score",
                self.SEVERITY_VALUE.get(severity, 15.0),
            )
            or 0.0
        )
        risk = min(100.0, max(0.0, float(item.get("risk_score", 0.0) or 0.0)))
        effort = min(100.0, max(0.0, float(item.get("effort_score", 0.0) or 0.0)))
        confidence = min(
            1.0,
            max(0.0, float(item.get("confidence", 0.5) or 0.0)),
        )
        fingerprint = str(item.get("fingerprint", "")).strip()
        completed_bonus = (
            -25.0
            if fingerprint and fingerprint in (completed_fingerprints or set())
            else 0.0
        )
        failure_penalty = (
            -15.0
            if fingerprint and fingerprint in (failed_fingerprints or set())
            else 0.0
        )
        issue_type = str(item.get("issue_type", "")).upper().strip()
        issue_failures = int(
            (failed_issue_type_counts or {}).get(issue_type, 0)
            if issue_type
            else 0
        )
        issue_failure_penalty = -20.0 * min(2, max(0, issue_failures))
        final_score = round(
            value
            + confidence * 25.0
            - risk * 0.55
            - effort * 0.30
            + completed_bonus
            + failure_penalty
            + issue_failure_penalty,
            2,
        )
        item["final_score"] = final_score
        item["ranking"] = {
            "value": value,
            "risk": risk,
            "effort": effort,
            "confidence": confidence,
            "completed_bonus": completed_bonus,
            "failure_penalty": failure_penalty,
            "issue_failure_penalty": issue_failure_penalty,
            "issue_failures": issue_failures,
        }
        return item

    def select_best(
        self,
        opportunities: list[dict[str, Any]],
        *,
        min_score: float,
        max_risk: float,
        min_confidence: float,
    ) -> dict[str, Any] | None:
        candidates: list[dict[str, Any]] = []
        completed_fingerprints = {
            str(item.get("fingerprint", ""))
            for item in opportunities
            if str(item.get("status", "")).upper() == "COMPLETED"
        }
        failed_fingerprints = {
            str(item.get("fingerprint", ""))
            for item in opportunities
            if str(item.get("status", "")).upper() == "FAILED"
        }
        failed_issue_type_counts: dict[str, int] = {}
        for item in opportunities:
            if not self._counts_as_issue_type_failure(item):
                continue
            issue_type = str(item.get("issue_type", "")).upper().strip()
            if issue_type:
                failed_issue_type_counts[issue_type] = (
                    failed_issue_type_counts.get(issue_type, 0) + 1
                )
        for source in opportunities:
            status = str(source.get("status", "PENDING")).upper()
            if status in ACTIVE_OPPORTUNITY_STATES:
                continue
            if status in TERMINAL_OPPORTUNITY_STATES:
                continue
            scored = self.score(
                source,
                completed_fingerprints=completed_fingerprints,
                failed_fingerprints=failed_fingerprints,
                failed_issue_type_counts=failed_issue_type_counts,
            )
            if float(scored.get("risk_score", 0.0) or 0.0) > float(max_risk):
                continue
            if float(scored.get("confidence", 0.0) or 0.0) < float(min_confidence):
                continue
            if float(scored.get("final_score", 0.0) or 0.0) < float(min_score):
                continue
            candidates.append(scored)
        candidates.sort(
            key=lambda item: (
                float(item.get("final_score", 0.0) or 0.0),
                float(item.get("confidence", 0.0) or 0.0),
                -float(item.get("risk_score", 0.0) or 0.0),
                str(item.get("created_at", "")),
            ),
            reverse=True,
        )
        return dict(candidates[0]) if candidates else None

    @staticmethod
    def _counts_as_issue_type_failure(item: dict[str, Any]) -> bool:
        if str(item.get("status", "")).upper() != "FAILED":
            return False
        error = str(item.get("last_error", "")).casefold()
        infrastructure_markers = (
            "target już istnieje",
            "already exists",
            "podaj katalog modułu",
            "nie pojedynczy plik",
            "target_conflict",
        )
        return not any(marker in error for marker in infrastructure_markers)
