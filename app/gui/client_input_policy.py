from __future__ import annotations


def should_block_client_input(
    *,
    presenter_busy: bool,
    has_pending_confirmation: bool,
) -> bool:
    """Block new tasks, but always allow answers and revisions to a pending plan."""
    return bool(presenter_busy and not has_pending_confirmation)
