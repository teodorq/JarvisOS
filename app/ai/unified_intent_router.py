from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import unicodedata
from typing import Any


@dataclass(frozen=True, slots=True)
class IntentDecision:
    """Normalized owner intent with evidence and safe execution defaults."""

    intent: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    auto_approve: bool = False
    auto_deploy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UnifiedIntentRouter:
    """Concept router for autonomous development owner commands.

    The router intentionally recognizes concepts instead of complete phrases.
    It is the migration point for older command-specific marker lists.
    """

    DEVELOPMENT = (
        "autodev", "autonomiczn", "backlog", "kod", "projekt",
        "program", "samoprogram", "rozwoj", "samorozw", "rozwij", "ulepsz", "popraw", "refaktor", "patch",
    )
    ACTION_START = (
        "uruchom", "zaczn", "rozpoczn", "pracuj", "wykon", "przygot",
        "wybierz", "analizuj", "rozwij", "ulepsz", "programuj",
    )
    ACTION_STATUS = ("status", "stan", "postep", "robi", "dzieje")
    ACTION_RESUME = ("wznow", "kontynu", "odzysk", "restart", "przerwan")
    ACTION_CANCEL = ("anul", "zatrzym", "przerwij", "odrzuc")
    ACTION_REVIEW = ("pokaz", "przejrz", "podglad", "raport", "lista", "szczegol")
    PATCH_OBJECT = ("patch", "popraw")
    DEPLOYMENT = ("wdroz", "instal", "zainstal", "zastosuj", "produkcyj")
    MULTI = (
        "wiele", "kilka", "kolejn", "seri", "kampani", "dlug", "ciagle",
        "samodziel",
    )
    SINGLE = ("jeden", "jedno", "jedna", "pojedyncz", "cykl")
    SELF_DIRECTED = (
        "samorozw", "rozwij siebie", "rozwijaj siebie", "rozwijaj sie",
        "sam sie rozwij", "ulepsz siebie", "programuj siebie",
        "programuj sie", "sam sie programuj", "samoprogram",
    )
    FOREIGN = (
        "kalendar", "spotkan", "mail", "wiadom", "dokument", "przegladark",
        "pogod", "muzyk", "uczenia napraw",
    )
    NUMBER_WORDS = {
        "jeden": 1, "jedno": 1, "jedna": 1, "dwa": 2, "dwie": 2,
        "trzy": 3, "cztery": 4, "piec": 5, "szesc": 6,
        "siedem": 7, "osiem": 8, "dziewiec": 9, "dziesiec": 10,
    }

    def route(self, command: str) -> IntentDecision | None:
        normalized = self.normalize(command)
        if not normalized:
            return None
        tokens = tuple(normalized.split())
        evidence: list[str] = []
        development = self._matching(tokens, self.DEVELOPMENT)
        self_directed = bool(self._matching(tokens, self.SELF_DIRECTED))
        foreign = self._matching(tokens, self.FOREIGN)
        if foreign and not self._strong_development_scope(tokens):
            return None
        if not development:
            return None
        evidence.extend(f"scope:{item}" for item in development[:3])

        deployment = self._matching(tokens, self.DEPLOYMENT)
        no_deploy = self._explicit_no_deploy(normalized)
        if deployment and not no_deploy:
            return IntentDecision(
                intent="autodev_deployment_blocked",
                confidence=0.99,
                entities={"requested_operation": "deployment"},
                evidence=tuple(evidence + ["safety:deployment-request"]),
            )

        patch_scope = bool(self._matching(tokens, self.PATCH_OBJECT))
        campaign_scope = bool(self._matching(tokens, self.MULTI)) or self._contains(
            tokens, ("autodev",)
        )
        if patch_scope and campaign_scope:
            patch_index = self._task_count(tokens)
            if self._contains(tokens, ("odrzuc", "usun")):
                return IntentDecision(
                    intent="autodev_campaign_discard_patch",
                    confidence=0.96,
                    entities={"patch_index": patch_index},
                    evidence=tuple(evidence + ["operation:discard-patch"]),
                )
            if self._matching(tokens, self.ACTION_REVIEW):
                return IntentDecision(
                    intent="autodev_campaign_review",
                    confidence=0.94,
                    entities={"patch_index": patch_index},
                    evidence=tuple(evidence + ["operation:review"]),
                )

        operation = self._operation(tokens, stop_before_deployment=no_deploy)
        if operation == "start":
            count = self._task_count(tokens)
            multi = (bool(self._matching(tokens, self.MULTI)) or bool(
                count is not None and count > 1
            )) and not self_directed
            explicit_single = self_directed or count == 1 or (
                bool(self._matching(tokens, self.SINGLE)) and not multi
            ) or any(token in {"zadanie", "poprawke"} for token in tokens)
            if not explicit_single and not multi:
                return None
            intent = (
                "autodev_cycle_run"
                if explicit_single
                else "autodev_campaign_start"
            )
            return IntentDecision(
                intent=intent,
                confidence=self._confidence(development, operation, multi),
                entities={
                    "max_tasks": 1 if explicit_single else (count or 5),
                    "background": not explicit_single,
                    "stop_before_deployment": True,
                },
                evidence=tuple(
                    evidence
                    + [f"operation:{operation}", f"mode:{'single' if explicit_single else 'campaign'}"]
                ),
            )

        recovery_scope = (
            operation == "resume"
            and len(self._matching(tokens, self.ACTION_RESUME)) >= 2
        )
        multi_scope = bool(self._matching(tokens, self.MULTI)) or recovery_scope
        cycle_scope = (self_directed or self._contains(tokens, ("cykl",))) and not multi_scope
        if not cycle_scope and not multi_scope:
            return None
        suffix = {
            "status": "status",
            "resume": "resume",
            "cancel": "cancel",
        }.get(operation)
        if suffix is None:
            return None
        intent = (
            f"autodev_cycle_{suffix}"
            if cycle_scope
            else f"autodev_campaign_{suffix}"
        )
        return IntentDecision(
            intent=intent,
            confidence=self._confidence(development, operation, not cycle_scope),
            entities={"background": operation == "resume" and not cycle_scope},
            evidence=tuple(evidence + [f"operation:{operation}"]),
        )

    def _operation(
        self,
        tokens: tuple[str, ...],
        *,
        stop_before_deployment: bool = False,
    ) -> str:
        if stop_before_deployment and self._matching(tokens, self.ACTION_START):
            return "start"
        groups = (
            ("cancel", self.ACTION_CANCEL),
            ("resume", self.ACTION_RESUME),
            ("status", self.ACTION_STATUS),
            ("start", self.ACTION_START),
        )
        for operation, stems in groups:
            if self._matching(tokens, stems):
                return operation
        return ""

    def _task_count(self, tokens: tuple[str, ...]) -> int | None:
        for token in tokens:
            if token.isdigit():
                return min(10, max(1, int(token)))
            for word, count in self.NUMBER_WORDS.items():
                if token.startswith(word):
                    return count
        return None

    def _strong_development_scope(self, tokens: tuple[str, ...]) -> bool:
        return self._contains(tokens, ("autodev", "backlog", "kod", "program"))

    @classmethod
    def _matching(
        cls,
        tokens: tuple[str, ...],
        stems: tuple[str, ...],
    ) -> list[str]:
        return [stem for stem in stems if cls._contains(tokens, (stem,))]

    @staticmethod
    def _contains(tokens: tuple[str, ...], stems: tuple[str, ...]) -> bool:
        for stem in stems:
            parts = stem.split()
            if len(parts) > 1:
                joined = " ".join(tokens)
                if stem in joined:
                    return True
                continue
            if any(token.startswith(stem) for token in tokens):
                return True
        return False

    @staticmethod
    def _explicit_no_deploy(normalized: str) -> bool:
        release = r"(?:wdro\w*|instal\w*|zainstal\w*|zastos\w*)"
        return bool(re.search(
            rf"\b(?:"
            rf"nie\s+{release}|"
            rf"bez\s+(?:\w+\s+){{0,2}}{release}|"
            rf"przed\s+(?:\w+\s+)?{release}|"
            rf"zatrzymaj\s+(?:\w+\s+)?przed\s+{release}"
            rf")",
            normalized,
        ))

    @staticmethod
    def _confidence(
        development: list[str],
        operation: str,
        multi: bool,
    ) -> float:
        score = 0.64 + min(0.18, len(development) * 0.06)
        if operation:
            score += 0.1
        if multi:
            score += 0.04
        return round(min(0.99, score), 2)

    @staticmethod
    def normalize(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value).casefold())
        plain = "".join(char for char in text if not unicodedata.combining(char))
        return " ".join(
            "".join(char if char.isalnum() else " " for char in plain).split()
        )


DEFAULT_INTENT_ROUTER = UnifiedIntentRouter()
