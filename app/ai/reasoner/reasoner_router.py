from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ReasonerRoute(str, Enum):
    REASON = "REASON"
    ANALYZE = "ANALYZE"
    EXECUTE = "EXECUTE"
    APPROVE = "APPROVE"
    ATTACH_RESEARCH = "ATTACH_RESEARCH"
    SESSION_STATUS = "SESSION_STATUS"
    MEMORY_SUMMARY = "MEMORY_SUMMARY"
    FIND_SIMILAR = "FIND_SIMILAR"
    NONE = "NONE"


@dataclass
class ReasonerRouteResult:
    matched: bool
    route: str
    confidence: float
    command: str
    payload: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReasonerRouter:

    REASON_PREFIXES = (
        "rozumuj",
        "przeanalizuj cel",
        "wybierz najlepsze rozwiązanie",
        "oceń opcje",
        "zbuduj strategię",
        "zbuduj strategie",
        "podejmij decyzję",
        "podejmij decyzje",
        "reason",
        "reasoning",
    )

    ANALYZE_PREFIXES = (
        "przeanalizuj bez wykonywania",
        "tylko przeanalizuj",
        "analiza reasonera",
        "reasoner analiza",
    )

    EXECUTE_PREFIXES = (
        "wykonaj sesję reasonera",
        "wykonaj sesje reasonera",
        "uruchom sesję reasonera",
        "uruchom sesje reasonera",
        "wykonaj strategię",
        "wykonaj strategie",
    )

    APPROVE_PREFIXES = (
        "zaakceptuj sesję",
        "zaakceptuj sesje",
        "zatwierdź sesję",
        "zatwierdz sesje",
        "odrzuć sesję",
        "odrzuc sesje",
    )

    ATTACH_RESEARCH_PREFIXES = (
        "dołącz research do sesji",
        "dolacz research do sesji",
        "przypisz research do sesji",
    )

    SESSION_STATUS_PREFIXES = (
        "status sesji reasonera",
        "pokaż sesję reasonera",
        "pokaz sesje reasonera",
        "podsumuj sesję reasonera",
        "podsumuj sesje reasonera",
    )

    MEMORY_PREFIXES = (
        "pamięć reasonera",
        "pamiec reasonera",
        "podsumowanie pamięci reasonera",
        "podsumowanie pamieci reasonera",
        "statystyki reasonera",
    )

    FIND_SIMILAR_PREFIXES = (
        "znajdź podobne decyzje",
        "znajdz podobne decyzje",
        "podobne decyzje reasonera",
        "historia podobnych strategii",
    )

    def route(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_command = self._normalize_text(command)
        normalized_context = (
            dict(context)
            if isinstance(context, dict)
            else {}
        )

        if not normalized_command:
            return self._result(
                matched=False,
                route=ReasonerRoute.NONE,
                confidence=0.0,
                command=command,
                payload={},
                metadata={"reason": "empty_command"},
            )

        explicit_route = self._detect_explicit_route(
            normalized_command
        )

        if explicit_route != ReasonerRoute.NONE:
            payload = self._build_payload(
                route=explicit_route,
                command=command,
                normalized_command=normalized_command,
                context=normalized_context,
            )

            return self._result(
                matched=True,
                route=explicit_route,
                confidence=0.98,
                command=command,
                payload=payload,
                metadata={
                    "router_version": "1.0.0",
                    "match_type": "explicit",
                },
            )

        inferred_route, confidence = self._infer_route(
            normalized_command,
            normalized_context,
        )

        if inferred_route == ReasonerRoute.NONE:
            return self._result(
                matched=False,
                route=ReasonerRoute.NONE,
                confidence=confidence,
                command=command,
                payload={},
                metadata={
                    "router_version": "1.0.0",
                    "match_type": "none",
                },
            )

        payload = self._build_payload(
            route=inferred_route,
            command=command,
            normalized_command=normalized_command,
            context=normalized_context,
        )

        return self._result(
            matched=True,
            route=inferred_route,
            confidence=confidence,
            command=command,
            payload=payload,
            metadata={
                "router_version": "1.0.0",
                "match_type": "inferred",
            },
        )

    def classify(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.route(command=command, context=context)

    def match(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        return bool(
            self.route(
                command=command,
                context=context,
            ).get("matched")
        )

    def _detect_explicit_route(
        self,
        command: str,
    ) -> ReasonerRoute:

        prefix_map = [
            (ReasonerRoute.ATTACH_RESEARCH, self.ATTACH_RESEARCH_PREFIXES),
            (ReasonerRoute.SESSION_STATUS, self.SESSION_STATUS_PREFIXES),
            (ReasonerRoute.MEMORY_SUMMARY, self.MEMORY_PREFIXES),
            (ReasonerRoute.FIND_SIMILAR, self.FIND_SIMILAR_PREFIXES),
            (ReasonerRoute.APPROVE, self.APPROVE_PREFIXES),
            (ReasonerRoute.EXECUTE, self.EXECUTE_PREFIXES),
            (ReasonerRoute.ANALYZE, self.ANALYZE_PREFIXES),
            (ReasonerRoute.REASON, self.REASON_PREFIXES),
        ]

        for route, prefixes in prefix_map:
            if any(command.startswith(prefix) for prefix in prefixes):
                return route

        return ReasonerRoute.NONE

    def _infer_route(
        self,
        command: str,
        context: dict[str, Any],
    ) -> tuple[ReasonerRoute, float]:

        if self._contains_session_reference(command):
            if self._contains_any(
                command,
                ("zaakceptuj", "zatwierdź", "zatwierdz", "odrzuć", "odrzuc"),
            ):
                return ReasonerRoute.APPROVE, 0.93

            if self._contains_any(
                command,
                ("wykonaj", "uruchom", "kontynuuj"),
            ):
                return ReasonerRoute.EXECUTE, 0.90

            if self._contains_any(
                command,
                ("status", "pokaż", "pokaz", "podsumuj"),
            ):
                return ReasonerRoute.SESSION_STATUS, 0.88

        if self._contains_any(
            command,
            (
                "kilka rozwiązań",
                "kilka rozwiazan",
                "porównaj opcje",
                "porownaj opcje",
                "oceń ryzyko",
                "ocen ryzyko",
                "wybierz strategię",
                "wybierz strategie",
                "najlepsza decyzja",
                "najbezpieczniejsze rozwiązanie",
                "najbezpieczniejsze rozwiazanie",
            ),
        ):
            return ReasonerRoute.REASON, 0.89

        if self._contains_any(
            command,
            (
                "reasoner",
                "reasoning",
                "goalreasoner",
                "decisiongraph",
                "optiongenerator",
                "riskevaluator",
                "strategybuilder",
            ),
        ):
            return ReasonerRoute.REASON, 0.84

        if context.get("force_reasoner") is True:
            return ReasonerRoute.REASON, 0.99

        return ReasonerRoute.NONE, 0.15

    def _build_payload(
        self,
        route: ReasonerRoute,
        command: str,
        normalized_command: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:

        payload: dict[str, Any] = {
            "command": command.strip(),
            "context": dict(context),
        }

        if route in {
            ReasonerRoute.REASON,
            ReasonerRoute.ANALYZE,
        }:
            payload["user_request"] = self._extract_request(
                normalized_command,
                route,
            )
            payload["auto_execute"] = (
                route == ReasonerRoute.REASON
                and bool(context.get("auto_execute", False))
            )
            payload["approved"] = context.get("approved")
            payload["research_context"] = context.get("research_context")
            payload["project_context"] = context.get("project_context")

        elif route == ReasonerRoute.EXECUTE:
            payload["session_id"] = (
                self._extract_session_id(command)
                or context.get("session_id")
            )
            payload["approved"] = context.get("approved")

        elif route == ReasonerRoute.APPROVE:
            payload["session_id"] = (
                self._extract_session_id(command)
                or context.get("session_id")
            )
            payload["approved"] = not self._contains_any(
                normalized_command,
                ("odrzuć", "odrzuc"),
            )
            payload["execute"] = bool(
                context.get("execute_after_approval", False)
            )
            payload["note"] = context.get("note")

        elif route == ReasonerRoute.ATTACH_RESEARCH:
            payload["session_id"] = (
                self._extract_session_id(command)
                or context.get("session_id")
            )
            payload["research_context"] = context.get(
                "research_context",
                {},
            )

        elif route == ReasonerRoute.SESSION_STATUS:
            payload["session_id"] = (
                self._extract_session_id(command)
                or context.get("session_id")
            )

        elif route == ReasonerRoute.FIND_SIMILAR:
            payload["goal"] = context.get("goal", {})
            payload["limit"] = self._safe_int(
                context.get("limit", 5),
                5,
            )

        return payload

    def _extract_request(
        self,
        command: str,
        route: ReasonerRoute,
    ) -> str:

        prefixes = (
            self.ANALYZE_PREFIXES
            if route == ReasonerRoute.ANALYZE
            else self.REASON_PREFIXES
        )

        for prefix in prefixes:
            if command.startswith(prefix):
                request = command[len(prefix):].strip(" :-")
                if request:
                    return request

        return command.strip()

    def _extract_session_id(
        self,
        command: str,
    ) -> str | None:

        marker = "reasoning_session_"
        index = command.find(marker)

        if index < 0:
            return None

        candidate = command[index:].split()[0]
        candidate = candidate.strip(".,;:()[]{}")

        return candidate or None

    def _contains_session_reference(
        self,
        command: str,
    ) -> bool:
        return "sesj" in command or "reasoning_session_" in command

    def _contains_any(
        self,
        text: str,
        phrases: tuple[str, ...],
    ) -> bool:
        return any(phrase in text for phrase in phrases)

    def _normalize_text(
        self,
        text: str,
    ) -> str:
        if not isinstance(text, str):
            return ""
        return " ".join(text.strip().lower().split())

    def _safe_int(
        self,
        value: Any,
        default: int,
    ) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _result(
        self,
        matched: bool,
        route: ReasonerRoute,
        confidence: float,
        command: str,
        payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:

        return ReasonerRouteResult(
            matched=matched,
            route=route.value,
            confidence=round(
                max(0.0, min(1.0, confidence)),
                2,
            ),
            command=str(command),
            payload=payload,
            metadata=metadata,
        ).to_dict()
