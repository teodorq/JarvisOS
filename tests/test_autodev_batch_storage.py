from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from app.ai.software_engineer.autonomous_learning_store import (
    AutonomousLearningStore,
)
from app.ai.software_engineer.strategic_development_store import (
    StrategicDevelopmentStore,
)
from app.ai.software_engineer.strategic_portfolio_store import (
    StrategicPortfolioStore,
)


def _goal(goal_id: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "fingerprint": f"fingerprint-{goal_id}",
        "title": f"Cel {goal_id}",
        "objective": "Bezpiecznie popraw projekt.",
        "subsystem": "app/ai",
        "issue_type": "LONG_FUNCTION",
    }


def _entry(goal_id: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "subsystem": "app/ai",
        "issue_type": "LONG_FUNCTION",
        "title": f"Cel {goal_id}",
    }


def test_episode_batch_performs_one_load_and_one_atomic_save() -> None:
    with TemporaryDirectory() as temporary:
        store = AutonomousLearningStore(temporary)
        with patch.object(
            store._store,
            "load",
            wraps=store._store.load,
        ) as load, patch.object(
            store._store,
            "save",
            wraps=store._store.save,
        ) as save:
            result = store.save_episodes([
                {"episode_id": "episode-1", "reward": 1.0},
                {"episode_id": "episode-2", "reward": 0.5},
                {"episode_id": "episode-1", "reward": 0.8},
            ])

        assert result == {"created": 2, "updated": 1, "total": 3}
        assert load.call_count == 1
        assert save.call_count == 1
        assert len(store.list_episodes()) == 2


def test_invalid_episode_batch_is_not_partially_persisted() -> None:
    with TemporaryDirectory() as temporary:
        store = AutonomousLearningStore(temporary)

        with pytest.raises(ValueError):
            store.save_episodes([
                {"episode_id": "valid-first"},
                {"episode_id": ""},
            ])

        assert store.list_episodes() == []


def test_goal_replacement_uses_one_atomic_save() -> None:
    with TemporaryDirectory() as temporary:
        store = StrategicDevelopmentStore(temporary)
        with patch.object(
            store._store,
            "load",
            wraps=store._store.load,
        ) as load, patch.object(
            store._store,
            "save",
            wraps=store._store.save,
        ) as save:
            result = store.replace_goals([_goal("goal-1"), _goal("goal-2")])

        assert load.call_count == 1
        assert save.call_count == 1
        assert {item["goal_id"] for item in result} == {"goal-1", "goal-2"}


def test_portfolio_replacement_uses_one_atomic_save() -> None:
    with TemporaryDirectory() as temporary:
        store = StrategicPortfolioStore(Path(temporary))
        with patch.object(
            store._store,
            "load",
            wraps=store._store.load,
        ) as load, patch.object(
            store._store,
            "save",
            wraps=store._store.save,
        ) as save:
            result = store.replace_entries([
                _entry("goal-1"),
                _entry("goal-2"),
            ])

        assert load.call_count == 1
        assert save.call_count == 1
        assert {item["goal_id"] for item in result} == {"goal-1", "goal-2"}
