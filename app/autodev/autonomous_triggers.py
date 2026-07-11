from __future__ import annotations

from typing import Any, Callable

from app.autodev.autonomous_policy import BackgroundAutonomyPolicy
from app.autodev.idle_detector import IdleDetector


class AutonomousTriggers:

    def __init__(
        self,
        *,
        policy: BackgroundAutonomyPolicy,
        idle_detector: IdleDetector | None = None,
        cpu_provider: Callable[[], float] | None = None,
    ) -> None:
        self.policy = policy
        self.idle_detector = idle_detector or IdleDetector()
        self.cpu_provider = cpu_provider or (lambda: 0.0)

    def evaluate(self) -> dict[str, Any]:
        idle_seconds = self.idle_detector.idle_seconds()
        cpu_percent = max(0.0, float(self.cpu_provider()))

        reasons: list[str] = []

        if not self.policy.enabled:
            reasons.append("Autonomia tła jest wyłączona.")

        if idle_seconds < self.policy.idle_seconds_required:
            reasons.append("Użytkownik nie jest wystarczająco długo bezczynny.")

        if cpu_percent > self.policy.max_cpu_percent:
            reasons.append("Użycie CPU jest zbyt wysokie.")

        return {
            "allowed": not reasons,
            "idle_seconds": idle_seconds,
            "cpu_percent": cpu_percent,
            "reasons": reasons,
        }
