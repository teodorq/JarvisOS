from typing import Any

class RegressionAnalyzer:
    def analyze(self, test_result: dict[str, Any]) -> dict[str, Any]:
        failures = [
            item
            for item in test_result.get("results", [])
            if not item.get("success", False)
        ]

        return {
            "success": not failures,
            "status": (
                "NO_REGRESSION"
                if not failures
                else "REGRESSION_DETECTED"
            ),
            "failures": failures,
            "failure_count": len(failures),
        }
