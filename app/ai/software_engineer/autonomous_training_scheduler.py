from __future__ import annotations

from typing import Any


class AutonomousTrainingScheduler:
    """Decides when enough new autonomy history exists for training."""

    def __init__(
        self,
        *,
        minimum_observations: int = 5,
        minimum_new_episodes: int = 1,
    ) -> None:
        self.minimum_observations = min(
            1000,
            max(1, int(minimum_observations)),
        )
        self.minimum_new_episodes = min(
            1000,
            max(1, int(minimum_new_episodes)),
        )

    def evaluate(
        self,
        *,
        summary: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        episodes = self._integer(summary.get("episodes", 0))
        last_count = self._integer(
            state.get("last_trained_episode_count", 0)
        )
        minimum_observations = self._integer(
            state.get(
                "minimum_observations",
                self.minimum_observations,
            )
        )
        minimum_new = self._integer(
            state.get(
                "minimum_new_episodes",
                self.minimum_new_episodes,
            )
        )
        minimum_observations = max(1, minimum_observations)
        minimum_new = max(1, minimum_new)
        new_episodes = max(0, episodes - last_count)

        if not bool(state.get("auto_training_enabled", True)):
            return self._result(
                "AUTONOMOUS_TRAINING_DISABLED",
                ready=False,
                episodes=episodes,
                new_episodes=new_episodes,
                minimum_observations=minimum_observations,
                minimum_new_episodes=minimum_new,
            )

        if bool(state.get("training_in_progress", False)):
            return self._result(
                "AUTONOMOUS_TRAINING_BUSY",
                ready=False,
                episodes=episodes,
                new_episodes=new_episodes,
                minimum_observations=minimum_observations,
                minimum_new_episodes=minimum_new,
            )

        if episodes < minimum_observations:
            return self._result(
                "AUTONOMOUS_TRAINING_WAITING_FOR_DATA",
                ready=False,
                episodes=episodes,
                new_episodes=new_episodes,
                minimum_observations=minimum_observations,
                minimum_new_episodes=minimum_new,
            )

        if new_episodes < minimum_new:
            return self._result(
                "AUTONOMOUS_TRAINING_WAITING_FOR_NEW_DATA",
                ready=False,
                episodes=episodes,
                new_episodes=new_episodes,
                minimum_observations=minimum_observations,
                minimum_new_episodes=minimum_new,
            )

        return self._result(
            "AUTONOMOUS_TRAINING_READY",
            ready=True,
            episodes=episodes,
            new_episodes=new_episodes,
            minimum_observations=minimum_observations,
            minimum_new_episodes=minimum_new,
        )

    @staticmethod
    def _result(
        status: str,
        *,
        ready: bool,
        episodes: int,
        new_episodes: int,
        minimum_observations: int,
        minimum_new_episodes: int,
    ) -> dict[str, Any]:
        return {
            "success": True,
            "status": status,
            "ready": bool(ready),
            "episodes": int(episodes),
            "new_episodes": int(new_episodes),
            "minimum_observations": int(minimum_observations),
            "minimum_new_episodes": int(minimum_new_episodes),
            "errors": [],
        }

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
