from __future__ import annotations

from typing import Any


class GmailReliabilityGate:
    """B190 release gate for the bounded live Gmail workflow."""

    @staticmethod
    def evaluate(status: dict[str, Any]) -> dict[str, Any]:
        gates = {
            "live_search": bool(status.get("search")),
            "full_message_read": bool(status.get("full_message_read")),
            "thread_read": bool(status.get("thread_read")),
            "threaded_reply_draft": bool(status.get("threaded_reply_draft")),
            "verified_send": bool(status.get("verified_send")),
            "confirmation_required": bool(status.get("send_requires_confirmation")),
            "automatic_sending_disabled": not bool(status.get("automatic_sending")),
        }
        passed = sum(bool(value) for value in gates.values())
        return {
            "status": "B186_B190_GMAIL_LIVE_READY" if passed == len(gates) else "BLOCKED",
            "passed": passed,
            "total": len(gates),
            "gates": gates,
        }
