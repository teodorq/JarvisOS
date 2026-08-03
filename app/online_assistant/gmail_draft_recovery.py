from __future__ import annotations

from typing import Any

from app.online_assistant.common import OnlineAssistantError, utc_now


class GmailDraftRecoveryService:
    """Recover the exact JARVIS draft from live Gmail after restart or stale state."""

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    def resolve(
        self,
        local: dict[str, Any] | None,
        selected: dict[str, Any] | None,
    ) -> dict[str, Any]:
        saved = dict(local or {})
        current = self._exact(saved)
        if current:
            return self._merge(saved, current, repaired=bool(saved.get("sent")))

        drafts = self._list()
        candidate = self._best(drafts, saved, dict(selected or {}))
        if not candidate:
            return {}
        return self._merge(saved, candidate, repaired=True)

    def exists(self, draft_id: object) -> bool:
        value = str(draft_id or "").strip()
        return bool(value and self._exact({"draft_id": value}))

    def _exact(self, saved: dict[str, Any]) -> dict[str, Any]:
        draft_id = str(saved.get("draft_id", "") or "").strip()
        getter = getattr(self.provider, "get_gmail_draft", None)
        if not draft_id or not callable(getter):
            return {}
        try:
            return dict(getter(draft_id) or {})
        except OnlineAssistantError:
            return {}
        except Exception:
            return {}

    def _list(self) -> list[dict[str, Any]]:
        loader = getattr(self.provider, "list_gmail_drafts", None)
        if not callable(loader):
            return []
        try:
            return [dict(item or {}) for item in loader(max_results=20)]
        except Exception:
            return []

    @classmethod
    def _best(
        cls,
        drafts: list[dict[str, Any]],
        saved: dict[str, Any],
        selected: dict[str, Any],
    ) -> dict[str, Any]:
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for index, item in enumerate(drafts):
            score = cls._score(item, saved, selected)
            if score >= 50:
                ranked.append((score, -index, item))
        if not ranked:
            return {}
        ranked.sort(key=lambda value: (value[0], value[1]), reverse=True)
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0] < 90:
            return {}
        return dict(ranked[0][2])

    @staticmethod
    def _score(
        item: dict[str, Any], saved: dict[str, Any], selected: dict[str, Any]
    ) -> int:
        same = lambda key, other: bool(
            str(item.get(key, "") or "").strip()
            and str(item.get(key, "") or "").strip()
            == str(other.get(key, "") or "").strip()
        )
        score = 0
        score += 120 if same("draft_id", saved) else 0
        score += 90 if same("message_id", saved) else 0
        score += 70 if same("thread_id", saved) else 0
        score += 65 if same("thread_id", selected) else 0
        score += 35 if same("subject", saved) else 0
        score += 30 if same("recipient", saved) else 0
        score += 30 if same("recipient_email", saved) else 0
        return score

    @staticmethod
    def _merge(
        saved: dict[str, Any], live: dict[str, Any], *, repaired: bool
    ) -> dict[str, Any]:
        result = {**saved, **live}
        result.update({
            "sent": False,
            "recovered_from_gmail": bool(repaired),
            "recovered_at": utc_now() if repaired else str(saved.get("recovered_at", "")),
        })
        result.pop("sent_at", None)
        result.pop("sent_message_id", None)
        return result
