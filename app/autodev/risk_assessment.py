from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RiskAssessment:

    level: str = "unknown"

    score: float = 0.0

    reasons: list[str] = field(
        default_factory=list
    )

    recommendations: list[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_reason(
        self,
        text: str
    ):
        if text:
            self.reasons.append(text)

    def add_recommendation(
        self,
        text: str
    ):
        if text:
            self.recommendations.append(text)

    def summary(self):

        lines = [
            "RISK ASSESSMENT",
            f"Level: {self.level}",
            f"Score: {self.score:.2f}",
            ""
        ]

        if self.reasons:
            lines.append("Reasons:")

            for item in self.reasons:
                lines.append(
                    f"- {item}"
                )

        if self.recommendations:
            lines.append("")
            lines.append(
                "Recommendations:"
            )

            for item in self.recommendations:
                lines.append(
                    f"- {item}"
                )

        return "\n".join(lines)