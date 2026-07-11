from typing import Any

class MergeDecisionEngine:
    def decide(
        self,
        *,
        test_result: dict[str, Any],
        regression_result: dict[str, Any],
    ) -> dict[str, Any]:
        allowed = bool(
            test_result.get("success")
            and regression_result.get("success")
        )

        return {
            "success": allowed,
            "status": (
                "MERGE_ALLOWED"
                if allowed
                else "ROLLBACK_REQUIRED"
            ),
            "decision": (
                "MERGE"
                if allowed
                else "ROLLBACK"
            ),
        }
