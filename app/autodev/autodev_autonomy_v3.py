from __future__ import annotations

from typing import Any

from app.autodev.autodev_candidate_ranker import (
    AutoDevCandidateRanker,
)
from app.autodev.autodev_confidence_engine import (
    AutoDevConfidenceEngine,
)
from app.autodev.autodev_next_action_engine import (
    AutoDevNextActionEngine,
)


class AutoDevAutonomyV3:
    def __init__(
        self,
        autonomy_v2: Any,
        ranker: AutoDevCandidateRanker | None = None,
        confidence_engine: AutoDevConfidenceEngine | None = None,
        next_action_engine: AutoDevNextActionEngine | None = None,
    ) -> None:

        self.autonomy_v2 = autonomy_v2
        self.ranker = (
            ranker
            or AutoDevCandidateRanker()
        )
        self.confidence_engine = (
            confidence_engine
            or AutoDevConfidenceEngine()
        )
        self.next_action_engine = (
            next_action_engine
            or AutoDevNextActionEngine()
        )

        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:

        ranking = self.ranker.rank(
            candidates
        )

        selected = ranking.get(
            "selected"
        )

        if not isinstance(
            selected,
            dict,
        ):
            return self._finish(
                {
                    "success": True,
                    "status": "NO_CANDIDATES",
                    "writes_code": False,
                    "approved": False,
                }
            )

        confidence = self.confidence_engine.calculate(
            selected
        )

        action = self.next_action_engine.decide(
            confidence=confidence,
            candidate=selected,
        )

        if action["action"] != "SAFE_PREVIEW":
            return self._finish(
                {
                    "success": True,
                    "status": action["status"],
                    "ranking": ranking,
                    "confidence": confidence,
                    "action": action,
                    "writes_code": False,
                    "approved": False,
                }
            )

        cycle = self.autonomy_v2.run(
            [
                selected
            ]
        )

        return self._finish(
            {
                "success": bool(
                    cycle.get(
                        "success",
                        False,
                    )
                ),
                "status": "AUTONOMY_V3_COMPLETED",
                "ranking": ranking,
                "confidence": confidence,
                "action": action,
                "cycle": cycle,
                "writes_code": False,
                "approved": False,
            }
        )

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.last_result = dict(result)
        return dict(result)

    def status(self) -> dict[str, Any]:
        return {
            "last_result": self.last_result,
        }
