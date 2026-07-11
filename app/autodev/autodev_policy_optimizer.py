from __future__ import annotations

from typing import Any


class AutoDevPolicyOptimizer:
    def optimize(
        self,
        *,
        memory_summary: dict[str, Any],
        current_policy: dict[str, Any],
    ) -> dict[str, Any]:
        policy = dict(
            current_policy
        )

        average_score = float(
            memory_summary.get(
                "average_quality_score",
                0.0,
            )
            or 0.0
        )

        recommendations: list[str] = []

        if average_score < 50.0:
            policy[
                "max_risk_score"
            ] = min(
                float(
                    policy.get(
                        "max_risk_score",
                        65.0,
                    )
                ),
                50.0,
            )
            recommendations.append(
                "Obniżono próg ryzyka."
            )

        elif average_score >= 85.0:
            recommendations.append(
                "Polityka pozostaje stabilna."
            )

        else:
            recommendations.append(
                "Zachowano ostrożny tryb."
            )

        policy[
            "require_approval"
        ] = True

        policy[
            "dry_run"
        ] = True

        return {
            "success": True,
            "status": "POLICY_OPTIMIZED",
            "policy": policy,
            "recommendations": recommendations,
        }
