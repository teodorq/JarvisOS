from __future__ import annotations

import unittest

from app.ai.software_engineer.autonomous_diagnostics_analyzer import (
    AutonomousDiagnosticsAnalyzer,
)
from app.ai.software_engineer.long_running_autonomy_service import (
    LongRunningAutonomyService,
)


class B563ConstraintsPauseHardeningTests(unittest.TestCase):
    def test_analyzer_reads_nested_director_constraints_status(self) -> None:
        snapshot = {
            "response": {
                "status": "FULL_AUTONOMY_PAUSED",
                "autonomy_run": {
                    "director_result": {
                        "status": "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS",
                    },
                },
            },
            "identifiers": {"job_id": "longrun-test"},
        }
        evidence = {
            "statuses": ["FULL_AUTONOMY_PAUSED"],
            "errors": ["DEPENDENCY_PENDING"],
        }

        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            snapshot,
            evidence,
        )

        self.assertEqual(diagnostic.category, "CONSTRAINTS_PAUSE")
        self.assertFalse(diagnostic.retryable)
        self.assertFalse(diagnostic.repairable)

    def test_analyzer_score_below_minimum_beats_dependency(self) -> None:
        snapshot = {
            "response": {"status": "FULL_AUTONOMY_PAUSED"},
            "identifiers": {"job_id": "longrun-test"},
        }
        evidence = {
            "statuses": ["FULL_AUTONOMY_PAUSED"],
            "errors": ["SCORE_BELOW_MINIMUM", "DEPENDENCY_PENDING"],
        }

        diagnostic = AutonomousDiagnosticsAnalyzer().analyze(
            snapshot,
            evidence,
        )

        self.assertEqual(diagnostic.category, "CONSTRAINTS_PAUSE")

    def test_long_running_fallback_ignores_wrong_diagnostic(self) -> None:
        response = {
            "status": "FULL_AUTONOMY_PAUSED",
            "portfolio": {
                "status": "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS",
            },
        }
        diagnostic = {
            "category": "DEPENDENCY_BLOCKED",
            "root_cause": "Błędnie rozpoznana zależność.",
        }

        result = LongRunningAutonomyService._is_constraints_pause(
            response,
            diagnostic,
        )

        self.assertTrue(result)

    def test_long_running_fallback_reads_score_reason(self) -> None:
        response = {
            "status": "FULL_AUTONOMY_PAUSED",
            "director_run": {
                "reasons": ["SCORE_BELOW_MINIMUM"],
            },
        }

        result = LongRunningAutonomyService._is_constraints_pause(
            response,
            {"category": "DEPENDENCY_BLOCKED"},
        )

        self.assertTrue(result)

    def test_optimization_constraints_policy_is_not_pause_evidence(self) -> None:
        response = {
            "status": "FULL_AUTONOMY_PAUSED",
            "policy": {
                "optimization_constraints": {
                    "min_score": 50.0,
                },
            },
            "errors": ["DEPENDENCY_PENDING"],
        }

        result = LongRunningAutonomyService._is_constraints_pause(
            response,
            {"category": "DEPENDENCY_BLOCKED"},
        )

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
