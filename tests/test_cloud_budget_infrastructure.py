from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUDGET_SOURCE = (ROOT / "infra" / "azure" / "budget.bicep").read_text(
    encoding="utf-8"
)
SUBSCRIPTION_SOURCE = (
    ROOT / "infra" / "azure" / "subscription.bicep"
).read_text(encoding="utf-8")


class CloudBudgetInfrastructureTests(unittest.TestCase):
    def test_monthly_budget_and_all_alert_thresholds_are_declared(self) -> None:
        self.assertIn("Microsoft.Consumption/budgets@2024-08-01", BUDGET_SOURCE)
        self.assertIn("param budgetAmount string = '4.60'", BUDGET_SOURCE)
        self.assertIn("timeGrain: 'Monthly'", BUDGET_SOURCE)
        for threshold in (50, 80, 100):
            self.assertIn(f"threshold: {threshold}", BUDGET_SOURCE)
        self.assertEqual(BUDGET_SOURCE.count("thresholdType: 'Actual'"), 3)
        self.assertEqual(BUDGET_SOURCE.count("operator: 'GreaterThan'"), 3)

    def test_private_alert_address_is_a_secure_deployment_parameter(self) -> None:
        self.assertIn("@secure()", BUDGET_SOURCE)
        self.assertIn("param budgetAlertEmail string", BUDGET_SOURCE)
        self.assertNotIn("@gmail.com", BUDGET_SOURCE)
        self.assertIn("module costGuardrail './budget.bicep'", SUBSCRIPTION_SOURCE)
        self.assertIn("budgetAlertEmail: budgetAlertEmail", SUBSCRIPTION_SOURCE)


if __name__ == "__main__":
    unittest.main()
