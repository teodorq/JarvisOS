from app.autodev.project_analysis import (
    ProjectAnalysis
)
from app.autodev.reasoning_strategy import (
    ReasoningStrategy
)
from app.autodev.risk_assessment import (
    RiskAssessment
)


class ProjectReasoner:

    def analyze(
        self,
        goal: str
    ):

        analysis = ProjectAnalysis(
            goal=goal
        )

        risk = RiskAssessment()

        strategy = ReasoningStrategy(
            name="Safe Development",
            description=(
                "Bezpieczna strategia "
                "z backupem i walidacją."
            ),
            risk_limit=0.30,
            auto_execute=False,
            require_backup=True,
            require_validation=True
        )

        risk.level = "LOW"
        risk.score = 0.15

        risk.add_reason(
            "Brak wykrytych konfliktów."
        )

        risk.add_recommendation(
            "Wykonaj standardowy workflow AutoDev."
        )

        return {
            "analysis": analysis,
            "risk": risk,
            "strategy": strategy
        }