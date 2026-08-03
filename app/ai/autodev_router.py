from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from app.autodev.autodev_request import (
    AutoDevRequest,
)
from app.autodev.autodev_response import (
    AutoDevResponse,
)
from app.autodev.autodev_service import (
    AutoDevService,
)
from app.core.project_paths import resolve_project_root


class AutoDevRouter:
    """Routes natural-language commands to the existing AutoDev service."""

    _STATUS_PHRASES = (
        "pokaż status autodev",
        "pokaz status autodev",
        "status autodev",
        "autodev status",
    )

    _REPORT_PHRASES = (
        "pokaż raport autodev",
        "pokaz raport autodev",
        "raport autodev",
        "autodev raport",
        "autodev report",
    )

    _PREVIEW_PHRASES = (
        "pokaż podgląd patcha",
        "pokaz podglad patcha",
        "pokaż patch",
        "pokaz patch",
        "podgląd patcha",
        "podglad patcha",
        "preview autodev",
        "autodev preview",
    )

    _APPROVE_AND_EXECUTE_PHRASES = (
        "zaakceptuj i wykonaj",
        "zatwierdź i wykonaj",
        "zatwierdz i wykonaj",
        "zaakceptuj patch i wykonaj",
        "zatwierdź patch i wykonaj",
        "zatwierdz patch i wykonaj",
        "autodev approve and execute",
    )

    _APPROVE_PHRASES = (
        "zaakceptuj patch",
        "zatwierdź patch",
        "zatwierdz patch",
        "autodev approve",
    )

    _EXECUTE_PHRASES = (
        "wykonaj patch",
        "uruchom patch",
        "autodev execute",
    )

    _REJECT_PHRASES = (
        "odrzuć patch",
        "odrzuc patch",
        "autodev reject",
    )

    _ROLLBACK_PHRASES = (
        "cofnij ostatnią zmianę",
        "cofnij ostatnia zmiane",
        "rollback autodev",
        "autodev rollback",
        "cofnij patch",
    )

    _RESET_PHRASES = (
        "zresetuj autodev",
        "wyczyść autodev",
        "wyczysc autodev",
        "autodev reset",
    )

    _SEARCH_PHRASES = (
        "znajdź użycia",
        "znajdz uzycia",
        "znajdź odniesienia",
        "znajdz odniesienia",
        "wyszukaj w kodzie",
        "autodev search",
    )

    _ANALYZE_PHRASES = (
        "autodev",
        "przeanalizuj moduł",
        "przeanalizuj modul",
        "przeanalizuj projekt",
        "analiza projektu",
        "zaplanuj refaktoryzację",
        "zaplanuj refaktoryzacje",
        "przygotuj analizę",
        "przygotuj analize",
    )

    _QUERY_CLEANUP_PHRASES = (
        "jarvis",
        "autodev",
        "przeanalizuj projekt",
        "przeanalizuj moduł",
        "przeanalizuj modul",
        "przeanalizuj",
        "zaplanuj refaktoryzację",
        "zaplanuj refaktoryzacje",
        "zaplanuj",
        "przygotuj analizę",
        "przygotuj analize",
    )

    def __init__(
        self,
        project_root: str | None = None,
        *,
        service: AutoDevService | None = None,
    ) -> None:
        resolved_root = str(
            resolve_project_root(
                project_root
            )
        )
        self.service = service or AutoDevService(
            project_root=resolved_root,
        )

    def can_handle(
        self,
        command: str,
    ) -> bool:
        if not isinstance(command, str) or not command.strip():
            return False

        normalized = self._normalize(command)

        return self._contains_any(
            normalized,
            self._all_supported_phrases(),
        )

    def handle(
        self,
        command: str,
    ) -> str:
        request = self.route(command)
        response = self.service.handle(request)
        return self.format_response(response)

    def route(
        self,
        command: str,
    ) -> AutoDevRequest:
        if not isinstance(command, str):
            raise TypeError("command must be a string")

        normalized = self._normalize(command)

        if self._contains_any(normalized, self._STATUS_PHRASES):
            return self._request(command, "status")

        if self._contains_any(normalized, self._REPORT_PHRASES):
            return self._request(command, "report")

        if self._contains_any(normalized, self._PREVIEW_PHRASES):
            return self._request(command, "preview")

        if self._contains_any(
            normalized,
            self._APPROVE_AND_EXECUTE_PHRASES,
        ):
            return self._request(command, "approve_and_execute")

        if self._contains_any(normalized, self._APPROVE_PHRASES):
            return self._request(command, "approve")

        if self._contains_any(normalized, self._EXECUTE_PHRASES):
            return self._request(command, "execute")

        if self._contains_any(normalized, self._REJECT_PHRASES):
            reason = self._extract_after(
                command,
                ("ponieważ", "poniewaz", "bo"),
            )
            return self._request(
                command,
                "reject",
                reason=reason,
            )

        if self._contains_any(normalized, self._ROLLBACK_PHRASES):
            return self._request(command, "rollback")

        if self._contains_any(normalized, self._RESET_PHRASES):
            return self._request(command, "reset")

        if self._contains_any(normalized, self._SEARCH_PHRASES):
            query = self._clean_query(
                command,
                (*self._SEARCH_PHRASES, "autodev"),
            )
            return self._request(
                command,
                "search",
                query=query,
            )

        query = self._clean_query(
            command,
            self._QUERY_CLEANUP_PHRASES,
        )

        if not query:
            query = command.strip()

        return self._request(
            command,
            "analyze",
            query=query,
        )

    def format_response(
        self,
        response: AutoDevResponse,
    ) -> str:
        if response.report and response.report.strip():
            return response.report.strip()

        message = (response.message or "").strip()
        errors = [
            str(error).strip()
            for error in (response.errors or [])
            if str(error).strip()
        ]

        if response.success or not errors:
            return message

        error_text = " | ".join(errors)
        if not message:
            return error_text

        return f"{message} {error_text}".strip()

    def _request(
        self,
        command: str,
        operation: str,
        *,
        query: str = "",
        reason: str = "",
    ) -> AutoDevRequest:
        return AutoDevRequest(
            command=command,
            operation=operation,
            query=query,
            reason=reason,
        )

    def _normalize(
        self,
        text: str,
    ) -> str:
        collapsed = " ".join(text.lower().strip().split())
        decomposed = unicodedata.normalize("NFKD", collapsed)
        return "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )

    def _contains_any(
        self,
        text: str,
        phrases: Iterable[str],
    ) -> bool:
        return any(
            self._normalize(phrase) in text
            for phrase in phrases
        )

    def _clean_query(
        self,
        command: str,
        phrases: Iterable[str],
    ) -> str:
        query = command.strip()

        for phrase in sorted(
            set(phrases),
            key=len,
            reverse=True,
        ):
            query = self._replace_case_insensitive(
                query,
                phrase,
                "",
            )

        query = re.sub(r"\s+", " ", query)
        return query.strip(" ,.:;-")

    def _replace_case_insensitive(
        self,
        text: str,
        old: str,
        new: str,
    ) -> str:
        if not old:
            return text

        pattern = (
            r"(?<!\w)"
            + re.escape(old)
            + r"(?!\w)"
        )

        return re.sub(
            pattern,
            lambda _match: new,
            text,
            flags=re.IGNORECASE,
        )

    def _extract_after(
        self,
        command: str,
        markers: Iterable[str],
    ) -> str:
        normalized_command = self._normalize(command)

        for marker in markers:
            normalized_marker = self._normalize(marker)
            position = normalized_command.find(normalized_marker)

            if position == -1:
                continue

            # The normalized representation keeps the same character count
            # for the supported Polish markers used here.
            return command[
                position + len(marker):
            ].strip(" ,.:;-")

        return ""

    @classmethod
    def _all_supported_phrases(cls) -> tuple[str, ...]:
        return (
            *cls._STATUS_PHRASES,
            *cls._REPORT_PHRASES,
            *cls._PREVIEW_PHRASES,
            *cls._APPROVE_AND_EXECUTE_PHRASES,
            *cls._APPROVE_PHRASES,
            *cls._EXECUTE_PHRASES,
            *cls._REJECT_PHRASES,
            *cls._ROLLBACK_PHRASES,
            *cls._RESET_PHRASES,
            *cls._SEARCH_PHRASES,
            *cls._ANALYZE_PHRASES,
        )
