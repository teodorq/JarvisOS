from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.ai.software_engineer.autonomous_diagnostics_analyzer import (
    AutonomousDiagnosticsAnalyzer,
)
from app.ai.software_engineer.long_running_autonomy_service import (
    LongRunningAutonomyService,
)
from app.ai.software_engineer.project_intelligence_ranker import (
    ProjectOpportunityRanker,
)
from app.ai.software_engineer.self_directed_development_service import (
    SelfDirectedDevelopmentService,
)


class _LongRunningStore:
    def __init__(self) -> None:
        self.saved: dict[str, object] = {}
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def save_job(self, value: dict[str, object]) -> dict[str, object]:
        self.saved = dict(value)
        return dict(value)

    def record_event(
        self,
        event: str,
        *,
        job_id: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.events.append((event, job_id, dict(metadata or {})))


class _ObservedLongRunningStore:
    def get_job(self, job_id: str) -> dict[str, object] | None:
        if job_id != "longrun-deferred":
            return None
        return {
            "job_id": job_id,
            "state": "CANCELLED",
            "last_result": {
                "status": "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS",
                "diagnostic_category": "CONSTRAINTS_PAUSE",
            },
        }


class _OpportunityStore:
    def list_opportunities(self, **_: object) -> list[dict[str, object]]:
        return [
            {
                "opportunity_id": "opportunity-deferred",
                "job_id": "longrun-deferred",
                "status": "CANCELLED",
                "last_error": "Ograniczenia bezpieczeństwa.",
            }
        ]


class _SelfDirectedStore:
    def __init__(self) -> None:
        self.runtime_value: dict[str, object] = {
            "consecutive_failures": 1,
            "completed_total": 2,
            "failed_total": 3,
            "deferred_total": 0,
            "cooldown_until": "old",
        }
        self.history_values: list[dict[str, object]] = []
        self.observed: set[str] = set()

    def has_observed(self, job_id: str) -> bool:
        return job_id in self.observed

    def runtime(self) -> dict[str, object]:
        return dict(self.runtime_value)

    def policy(self) -> dict[str, object]:
        return {"cooldown_after_failure_seconds": 600.0}

    def update_runtime(
        self,
        updates: dict[str, object],
    ) -> dict[str, object]:
        self.runtime_value.update(updates)
        return dict(self.runtime_value)

    def mark_observed(self, job_id: str) -> None:
        self.observed.add(job_id)

    def record_history(
        self,
        value: dict[str, object],
    ) -> dict[str, object]:
        self.history_values.append(dict(value))
        return dict(value)


class B562SafeFailureLearningTests(unittest.TestCase):
    def test_constraints_pause_wins_over_dependency_pending(self) -> None:
        snapshot = {
            "response": {"status": "FULL_AUTONOMY_PAUSED"},
            "identifiers": {"job_id": "longrun-test"},
        }
        evidence = {
            "statuses": [
                "FULL_AUTONOMY_PAUSED",
                "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS",
            ],
            "errors": ["SCORE_BELOW_MINIMUM", "DEPENDENCY_PENDING"],
        }

        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            snapshot,
            evidence,
        )

        self.assertEqual(diagnostic.category, "CONSTRAINTS_PAUSE")
        self.assertFalse(diagnostic.retryable)
        self.assertFalse(diagnostic.repairable)

    def test_ranker_learns_from_real_issue_type_failure(self) -> None:
        failed = {
            "status": "FAILED",
            "issue_type": "LARGE_MODULE",
            "fingerprint": "failed-large",
            "last_error": "AI Code Review odrzucił niepełną propozycję.",
        }
        large = {
            "status": "PENDING",
            "issue_type": "LARGE_MODULE",
            "fingerprint": "next-large",
            "value_score": 70.0,
            "risk_score": 40.0,
            "effort_score": 20.0,
            "confidence": 0.95,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        safer = {
            "status": "PENDING",
            "issue_type": "LONG_FUNCTION",
            "fingerprint": "safer-function",
            "value_score": 55.0,
            "risk_score": 30.0,
            "effort_score": 20.0,
            "confidence": 0.95,
            "created_at": "2026-01-02T00:00:00+00:00",
        }

        selected = ProjectOpportunityRanker().select_best(
            [failed, large, safer],
            min_score=0.0,
            max_risk=100.0,
            min_confidence=0.0,
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["fingerprint"], "safer-function")

    def test_target_conflict_does_not_poison_issue_type(self) -> None:
        failed = {
            "status": "FAILED",
            "issue_type": "LARGE_MODULE",
            "fingerprint": "routing-failure",
            "last_error": "Target już istnieje i nie może być nadpisany.",
        }
        large = {
            "status": "PENDING",
            "issue_type": "LARGE_MODULE",
            "fingerprint": "next-large",
            "value_score": 70.0,
            "risk_score": 40.0,
            "effort_score": 20.0,
            "confidence": 0.95,
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        safer = {
            "status": "PENDING",
            "issue_type": "LONG_FUNCTION",
            "fingerprint": "safer-function",
            "value_score": 55.0,
            "risk_score": 30.0,
            "effort_score": 20.0,
            "confidence": 0.95,
            "created_at": "2026-01-02T00:00:00+00:00",
        }

        selected = ProjectOpportunityRanker().select_best(
            [failed, large, safer],
            min_score=0.0,
            max_risk=100.0,
            min_confidence=0.0,
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["fingerprint"], "next-large")

    def test_long_running_constraints_pause_is_terminal_deferral(self) -> None:
        service = LongRunningAutonomyService.__new__(
            LongRunningAutonomyService
        )
        service.store = _LongRunningStore()
        now = datetime(2026, 7, 17, tzinfo=timezone.utc)

        result = service._defer_constraints_pause(
            {
                "job_id": "longrun-test",
                "attempts": 2,
                "execution_context": {},
                "metadata": {},
                "last_result": {},
            },
            {"status": "FULL_AUTONOMY_PAUSED"},
            diagnostic={
                "diagnostic_id": "diagnostic-test",
                "category": "CONSTRAINTS_PAUSE",
                "root_cause": "Brak bezpiecznej kampanii.",
            },
            now=now,
        )

        self.assertEqual(result["state"], "CANCELLED")
        self.assertEqual(
            result["last_result"]["status"],
            "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS",
        )
        self.assertEqual(result["next_run_at"], "")
        self.assertEqual(
            service.store.events[0][0],
            "LONG_RUNNING_JOB_DEFERRED_CONSTRAINTS",
        )

    def test_b56_neutral_deferral_does_not_increment_failure(self) -> None:
        service = SelfDirectedDevelopmentService.__new__(
            SelfDirectedDevelopmentService
        )
        service.store = _SelfDirectedStore()
        service.project_intelligence = type(
            "ProjectIntelligence",
            (),
            {
                "store": _OpportunityStore(),
                "long_running_service": type(
                    "LongRunning",
                    (),
                    {"store": _ObservedLongRunningStore()},
                )(),
            },
        )()

        outcomes = service._observe_terminal_outcomes()

        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["status"], "DEFERRED_CONSTRAINTS")
        self.assertEqual(service.store.runtime_value["failed_total"], 3)
        self.assertEqual(service.store.runtime_value["deferred_total"], 1)
        self.assertEqual(service.store.runtime_value["consecutive_failures"], 1)
        self.assertEqual(service.store.runtime_value["cooldown_until"], "")
        self.assertTrue(service.store.history_values[0]["success"])


if __name__ == "__main__":
    unittest.main()
