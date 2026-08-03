from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from dataclasses import asdict, dataclass, field
from typing import Any

from app.autodev.dependency_risk_analyzer import (
    DependencyRiskAnalyzer,
)


@dataclass(slots=True)
class ChangePrediction:
    success: bool
    status: str
    target: str = ""
    change_type: str = ""
    predicted_scope: str = "LOCAL"
    affected_modules: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "LOW"
    requires_full_tests: bool = False
    requires_approval: bool = True
    recommendations: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChangePredictionEngine:
    """
    Przewiduje zakres i ryzyko planowanej zmiany.

    Działa wyłącznie analitycznie.
    """

    HIGH_IMPACT_TYPES = {
        "PUBLIC_API_CHANGE",
        "CLASS_REFACTOR",
        "LARGE_CLASS",
        "LONG_FUNCTION",
        "TOO_MANY_ARGUMENTS",
        "MULTI_FILE",
    }

    def __init__(
        self,
        project_root: str = default_project_root(),
        dependency_analyzer: (
            DependencyRiskAnalyzer | None
        ) = None,
    ) -> None:

        self.project_root = project_root

        self.dependency_analyzer = (
            dependency_analyzer
            or DependencyRiskAnalyzer(
                project_root=project_root
            )
        )

        self.last_result: ChangePrediction | None = None

    def predict(
        self,
        *,
        target: str,
        change_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChangePrediction:

        metadata = dict(
            metadata or {}
        )

        dependency_result = (
            self.dependency_analyzer.analyze(
                target
            )
        )

        if not dependency_result.success:
            return self._finish(
                ChangePrediction(
                    success=False,
                    status="DEPENDENCY_ANALYSIS_FAILED",
                    target=target,
                    change_type=change_type,
                    errors=list(
                        dependency_result.errors
                    ),
                )
            )

        normalized_type = str(
            change_type
        ).strip().upper()

        risk_score = float(
            dependency_result.risk_score
        )

        recommendations = list(
            dependency_result.reasons
        )

        if normalized_type in self.HIGH_IMPACT_TYPES:
            risk_score += 20.0
            recommendations.append(
                "Zmiana należy do kategorii wysokiego wpływu."
            )

        if bool(
            metadata.get(
                "public_api",
                False,
            )
        ):
            risk_score += 20.0
            recommendations.append(
                "Zmiana może dotyczyć publicznego API."
            )

        if bool(
            metadata.get(
                "recent_regression",
                False,
            )
        ):
            risk_score += 15.0
            recommendations.append(
                "Wykryto kontekst niedawnej regresji."
            )

        risk_score = min(
            round(risk_score, 2),
            100.0,
        )

        affected_count = len(
            dependency_result.affected_modules
        )

        predicted_scope = self._scope(
            affected_count=affected_count,
            change_type=normalized_type,
        )

        risk_level = self._risk_level(
            risk_score
        )

        requires_full_tests = bool(
            predicted_scope in {
                "PROJECT",
                "MULTI_MODULE",
            }
            or risk_level in {
                "HIGH",
                "CRITICAL",
            }
        )

        result = ChangePrediction(
            success=True,
            status="CHANGE_PREDICTION_READY",
            target=dependency_result.target,
            change_type=normalized_type,
            predicted_scope=predicted_scope,
            affected_modules=list(
                dependency_result.affected_modules
            ),
            risk_score=risk_score,
            risk_level=risk_level,
            requires_full_tests=requires_full_tests,
            requires_approval=True,
            recommendations=list(
                dict.fromkeys(
                    recommendations
                )
            ),
        )

        return self._finish(
            result
        )

    def _scope(
        self,
        *,
        affected_count: int,
        change_type: str,
    ) -> str:

        if change_type == "MULTI_FILE":
            return "PROJECT"

        if affected_count > 10:
            return "PROJECT"

        if affected_count > 2:
            return "MULTI_MODULE"

        return "LOCAL"

    def _risk_level(
        self,
        score: float,
    ) -> str:

        if score >= 75:
            return "CRITICAL"

        if score >= 50:
            return "HIGH"

        if score >= 25:
            return "MEDIUM"

        return "LOW"

    def _finish(
        self,
        result: ChangePrediction,
    ) -> ChangePrediction:

        self.last_result = result
        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": self.project_root,
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
            "dependency_analyzer": (
                self.dependency_analyzer.status()
            ),
        }
