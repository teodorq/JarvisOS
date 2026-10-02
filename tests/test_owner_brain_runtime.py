from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.gui.owner_brain_runtime import activate_owner_brain


def test_owner_core_is_swapped_only_when_activation_is_requested() -> None:
    lightweight = object()
    owner = object()
    window = SimpleNamespace(
        brain=lightweight,
        assistant=object(),
        project_root="C:/JarvisAI",
    )
    with patch(
        "app.gui.owner_brain_runtime.ensure_owner_brain",
        return_value=owner,
    ) as ensure:
        result = activate_owner_brain(window)
    assert result is owner
    assert window.brain is owner
    ensure.assert_called_once_with(
        lightweight, window.assistant, window.project_root
    )
