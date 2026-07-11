from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class ImprovementType(str, Enum):
    BUG_FIX = "BUG_FIX"
    REFACTOR = "REFACTOR"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"
    TESTING = "TESTING"
    DOCUMENTATION = "DOCUMENTATION"
    ARCHITECTURE = "ARCHITECTURE"
    RELIABILITY = "RELIABILITY"
    MAINTAINABILITY = "MAINTAINABILITY"
    UNKNOWN = "UNKNOWN"


class ImprovementSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImprovementStatus(str, Enum):
    DETECTED = "DETECTED"
    SELECTED = "SELECTED"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


@dataclass
class ImprovementCandidate:
    improvement_id: str
    title: str
    description: str
    improvement_type: str
    severity: str
    score: float
    confidence: float
    affected_files: list[str]
    affected_modules: list[str]
    evidence: list[str]
    risks: list[str]
    benefits: list[str]
    recommended_actions: list[str]
    status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImprovementDetectionResult:
    detection_id: str
    candidates: list[dict[str, Any]]
    selected_candidate_id: str | None
    highest_score: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImprovementDetector:

    KEYWORD_RULES = {
        ImprovementType.BUG_FIX.value: (
            "bug",
            "błąd",
            "blad",
            "exception",
            "traceback",
            "crash",
            "awaria",
            "nie działa",
            "nie dziala",
            "failed",
            "failure",
        ),
        ImprovementType.REFACTOR.value: (
            "refactor",
            "duplikacja",
            "duplicate",
            "zbyt długi",
            "zbyt dlugi",
            "complex",
            "legacy",
            "cleanup",
            "code smell",
        ),
        ImprovementType.PERFORMANCE.value: (
            "slow",
            "wolno",
            "wydajność",
            "wydajnosc",
            "latency",
            "memory leak",
            "cpu",
            "ram",
            "timeout",
        ),
        ImprovementType.SECURITY.value: (
            "security",
            "bezpieczeństwo",
            "bezpieczenstwo",
            "vulnerability",
            "podatność",
            "podatnosc",
            "secret",
            "token",
            "credential",
        ),
        ImprovementType.TESTING.value: (
            "test",
            "coverage",
            "regression",
            "brak testów",
            "brak testow",
            "unittest",
            "pytest",
        ),
        ImprovementType.DOCUMENTATION.value: (
            "documentation",
            "dokumentacja",
            "readme",
            "docstring",
            "instrukcja",
        ),
        ImprovementType.ARCHITECTURE.value: (
            "architecture",
            "architektura",
            "dependency cycle",
            "cykl zależności",
            "cykl zaleznosci",
            "coupling",
            "sprzężenie",
            "sprzezenie",
        ),
        ImprovementType.RELIABILITY.value: (
            "reliability",
            "stabilność",
            "stabilnosc",
            "retry",
            "rollback",
            "recovery",
            "resilience",
        ),
        ImprovementType.MAINTAINABILITY.value: (
            "maintainability",
            "utrzymanie",
            "czytelność",
            "czytelnosc",
            "naming",
            "structure",
            "struktura",
        ),
    }

    SEVERITY_SCORES = {
        ImprovementSeverity.LOW.value: 20.0,
        ImprovementSeverity.MEDIUM.value: 45.0,
        ImprovementSeverity.HIGH.value: 70.0,
        ImprovementSeverity.CRITICAL.value: 95.0,
    }

    def detect(
        self,
        analysis: dict[str, Any],
        project_context: dict[str, Any] | None = None,
        previous_cycles: list[dict[str, Any]] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:

        normalized_analysis = self._safe_dict(
            analysis
        )

        normalized_context = self._safe_dict(
            project_context
        )

        normalized_history = [
            dict(item)
            for item in (
                previous_cycles or []
            )
            if isinstance(item, dict)
        ]

        raw_items = self._collect_raw_items(
            normalized_analysis
        )

        candidates = [
            self._candidate_from_item(
                item=item,
                project_context=normalized_context,
                previous_cycles=normalized_history,
            )
            for item in raw_items
        ]

        candidates = self._deduplicate_candidates(
            candidates
        )

        candidates.sort(
            key=lambda item: (
                -item.score,
                -item.confidence,
                item.title.lower(),
            )
        )

        candidates = candidates[
            :max(
                1,
                int(limit),
            )
        ]

        selected_candidate_id = (
            candidates[0].improvement_id
            if candidates
            else None
        )

        highest_score = (
            candidates[0].score
            if candidates
            else 0.0
        )

        result = ImprovementDetectionResult(
            detection_id=f"improvement_detection_{uuid4().hex}",
            candidates=[
                candidate.to_dict()
                for candidate in candidates
            ],
            selected_candidate_id=selected_candidate_id,
            highest_score=round(
                highest_score,
                2,
            ),
            metadata={
                "detector_version": "1.0.0",
                "raw_items_count": len(
                    raw_items
                ),
                "candidates_count": len(
                    candidates
                ),
                "project_context_available": bool(
                    normalized_context
                ),
                "history_count": len(
                    normalized_history
                ),
            },
        )

        return result.to_dict()

    def analyze(
        self,
        analysis: dict[str, Any],
        project_context: dict[str, Any] | None = None,
        previous_cycles: list[dict[str, Any]] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:

        return self.detect(
            analysis=analysis,
            project_context=project_context,
            previous_cycles=previous_cycles,
            limit=limit,
        )

    def choose_best(
        self,
        detection_result: dict[str, Any],
    ) -> dict[str, Any] | None:

        candidates = detection_result.get(
            "candidates",
            []
        )

        if not isinstance(
            candidates,
            list,
        ):
            return None

        valid_candidates = [
            item
            for item in candidates
            if isinstance(item, dict)
        ]

        if not valid_candidates:
            return None

        valid_candidates.sort(
            key=lambda item: (
                -self._safe_float(
                    item.get(
                        "score",
                        0.0,
                    ),
                    0.0,
                ),
                -self._safe_float(
                    item.get(
                        "confidence",
                        0.0,
                    ),
                    0.0,
                ),
            )
        )

        selected = dict(
            valid_candidates[0]
        )

        selected["status"] = (
            ImprovementStatus.SELECTED.value
        )

        return selected

    def _collect_raw_items(
        self,
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:

        items: list[
            dict[str, Any]
        ] = []

        candidate_keys = (
            "problems",
            "issues",
            "findings",
            "improvements",
            "suggestions",
            "recommendations",
            "warnings",
            "errors",
            "code_smells",
            "risks",
        )

        for key in candidate_keys:
            value = analysis.get(
                key
            )

            items.extend(
                self._normalize_items(
                    value,
                    source=key,
                )
            )

        report = analysis.get(
            "report"
        )

        if isinstance(report, dict):
            for key in candidate_keys:
                value = report.get(
                    key
                )

                items.extend(
                    self._normalize_items(
                        value,
                        source=(
                            f"report.{key}"
                        ),
                    )
                )

        modules = analysis.get(
            "modules"
        )

        if isinstance(modules, list):
            for module in modules:
                if not isinstance(
                    module,
                    dict,
                ):
                    continue

                module_name = str(
                    module.get(
                        "name",
                        module.get(
                            "module",
                            "",
                        ),
                    )
                )

                for key in candidate_keys:
                    value = module.get(
                        key
                    )

                    module_items = self._normalize_items(
                        value,
                        source=(
                            f"module.{key}"
                        ),
                    )

                    for item in module_items:
                        affected_modules = (
                            self._safe_string_list(
                                item.get(
                                    "affected_modules",
                                    [],
                                )
                            )
                        )

                        if module_name:
                            affected_modules.append(
                                module_name
                            )

                        item[
                            "affected_modules"
                        ] = self._unique_strings(
                            affected_modules
                        )

                    items.extend(
                        module_items
                    )

        if not items:
            summary_text = self._extract_text(
                analysis
            )

            if summary_text:
                items.append(
                    {
                        "title": (
                            "Ogólne ulepszenie projektu"
                        ),
                        "description": summary_text,
                        "source": "analysis_summary",
                    }
                )

        return items

    def _normalize_items(
        self,
        value: Any,
        source: str,
    ) -> list[dict[str, Any]]:

        if value is None:
            return []

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                return []

            return [
                {
                    "title": normalized[
                        :120
                    ],
                    "description": normalized,
                    "source": source,
                }
            ]

        if isinstance(value, dict):
            return [
                {
                    **dict(value),
                    "source": value.get(
                        "source",
                        source,
                    ),
                }
            ]

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            result: list[
                dict[str, Any]
            ] = []

            for item in value:
                result.extend(
                    self._normalize_items(
                        item,
                        source=source,
                    )
                )

            return result

        return [
            {
                "title": str(value)[
                    :120
                ],
                "description": str(value),
                "source": source,
            }
        ]

    def _candidate_from_item(
        self,
        item: dict[str, Any],
        project_context: dict[str, Any],
        previous_cycles: list[dict[str, Any]],
    ) -> ImprovementCandidate:

        title = str(
            item.get(
                "title",
                item.get(
                    "name",
                    item.get(
                        "message",
                        "Wykryte ulepszenie",
                    ),
                ),
            )
        ).strip()

        description = str(
            item.get(
                "description",
                item.get(
                    "details",
                    item.get(
                        "message",
                        title,
                    ),
                ),
            )
        ).strip()

        combined_text = (
            f"{title} {description}"
        ).lower()

        improvement_type = self._detect_type(
            combined_text
        )

        severity = self._detect_severity(
            item=item,
            text=combined_text,
        )

        affected_files = self._collect_files(
            item,
            project_context,
        )

        affected_modules = (
            self._collect_modules(
                item,
                project_context,
            )
        )

        evidence = self._collect_evidence(
            item
        )

        risks = self._build_risks(
            improvement_type=improvement_type,
            severity=severity,
            affected_files=affected_files,
            affected_modules=affected_modules,
        )

        benefits = self._build_benefits(
            improvement_type
        )

        recommended_actions = (
            self._build_recommended_actions(
                improvement_type
            )
        )

        confidence = self._calculate_confidence(
            item=item,
            evidence=evidence,
            affected_files=affected_files,
            affected_modules=affected_modules,
        )

        score = self._calculate_score(
            severity=severity,
            confidence=confidence,
            improvement_type=improvement_type,
            affected_files=affected_files,
            affected_modules=affected_modules,
            previous_cycles=previous_cycles,
            text=combined_text,
        )

        return ImprovementCandidate(
            improvement_id=f"improvement_{uuid4().hex}",
            title=title or "Wykryte ulepszenie",
            description=description,
            improvement_type=improvement_type,
            severity=severity,
            score=score,
            confidence=confidence,
            affected_files=affected_files,
            affected_modules=affected_modules,
            evidence=evidence,
            risks=risks,
            benefits=benefits,
            recommended_actions=(
                recommended_actions
            ),
            status=ImprovementStatus.DETECTED.value,
            metadata={
                "source": item.get(
                    "source",
                    "unknown",
                ),
                "detector_version": "1.0.0",
                "raw_item": dict(item),
            },
        )

    def _detect_type(
        self,
        text: str,
    ) -> str:

        scores = {
            improvement_type: 0
            for improvement_type
            in self.KEYWORD_RULES
        }

        for improvement_type, keywords in (
            self.KEYWORD_RULES.items()
        ):
            for keyword in keywords:
                if keyword in text:
                    scores[
                        improvement_type
                    ] += 1

        best_type = max(
            scores,
            key=scores.get,
        )

        if scores[best_type] == 0:
            return ImprovementType.UNKNOWN.value

        return best_type

    def _detect_severity(
        self,
        item: dict[str, Any],
        text: str,
    ) -> str:

        explicit = item.get(
            "severity",
            item.get(
                "priority",
                item.get(
                    "risk_level",
                ),
            ),
        )

        if explicit is not None:
            normalized = str(
                explicit
            ).strip().upper()

            if normalized in {
                item.value
                for item
                in ImprovementSeverity
            }:
                return normalized

        critical_keywords = (
            "critical",
            "krytyczny",
            "data loss",
            "utrata danych",
            "security breach",
            "crash",
            "system down",
        )

        high_keywords = (
            "high",
            "wysoki",
            "poważny",
            "powazny",
            "exception",
            "failed",
            "regression",
            "vulnerability",
        )

        medium_keywords = (
            "medium",
            "średni",
            "sredni",
            "warning",
            "slow",
            "duplicate",
            "code smell",
        )

        if any(
            keyword in text
            for keyword in critical_keywords
        ):
            return ImprovementSeverity.CRITICAL.value

        if any(
            keyword in text
            for keyword in high_keywords
        ):
            return ImprovementSeverity.HIGH.value

        if any(
            keyword in text
            for keyword in medium_keywords
        ):
            return ImprovementSeverity.MEDIUM.value

        return ImprovementSeverity.LOW.value

    def _calculate_score(
        self,
        severity: str,
        confidence: float,
        improvement_type: str,
        affected_files: list[str],
        affected_modules: list[str],
        previous_cycles: list[dict[str, Any]],
        text: str,
    ) -> float:

        score = self.SEVERITY_SCORES.get(
            severity,
            20.0,
        )

        score *= (
            0.5
            + confidence * 0.5
        )

        type_bonus = {
            ImprovementType.SECURITY.value: 12.0,
            ImprovementType.BUG_FIX.value: 10.0,
            ImprovementType.RELIABILITY.value: 8.0,
            ImprovementType.ARCHITECTURE.value: 6.0,
            ImprovementType.PERFORMANCE.value: 5.0,
            ImprovementType.TESTING.value: 4.0,
            ImprovementType.REFACTOR.value: 3.0,
            ImprovementType.MAINTAINABILITY.value: 2.0,
            ImprovementType.DOCUMENTATION.value: 1.0,
            ImprovementType.UNKNOWN.value: 0.0,
        }

        score += type_bonus.get(
            improvement_type,
            0.0,
        )

        score += min(
            10.0,
            len(affected_files) * 1.5,
        )

        score += min(
            10.0,
            len(affected_modules) * 2.0,
        )

        repeated_failures = 0

        for cycle in previous_cycles:
            if not isinstance(
                cycle,
                dict,
            ):
                continue

            cycle_result = str(
                cycle.get(
                    "result",
                    "",
                )
            ).upper()

            objective = str(
                cycle.get(
                    "objective",
                    "",
                )
            ).lower()

            if (
                cycle_result
                in {
                    "FAILED",
                    "ROLLED_BACK",
                }
                and objective
                and any(
                    word in objective
                    for word in text.split()[
                        :10
                    ]
                )
            ):
                repeated_failures += 1

        score += min(
            10.0,
            repeated_failures * 2.0,
        )

        return round(
            max(
                0.0,
                min(
                    100.0,
                    score,
                ),
            ),
            2,
        )

    def _calculate_confidence(
        self,
        item: dict[str, Any],
        evidence: list[str],
        affected_files: list[str],
        affected_modules: list[str],
    ) -> float:

        confidence = 0.45

        if item.get(
            "description"
        ):
            confidence += 0.10

        if item.get(
            "severity"
        ):
            confidence += 0.08

        if evidence:
            confidence += min(
                0.20,
                len(evidence) * 0.05,
            )

        if affected_files:
            confidence += 0.08

        if affected_modules:
            confidence += 0.05

        return round(
            max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            2,
        )

    def _collect_files(
        self,
        item: dict[str, Any],
        project_context: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        for key in (
            "affected_files",
            "files",
            "file",
            "paths",
            "path",
        ):
            values.extend(
                self._safe_list(
                    item.get(
                        key
                    )
                )
            )

        values.extend(
            self._safe_list(
                project_context.get(
                    "affected_files",
                    []
                )
            )
        )

        return self._unique_strings(
            values
        )

    def _collect_modules(
        self,
        item: dict[str, Any],
        project_context: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        for key in (
            "affected_modules",
            "modules",
            "module",
        ):
            values.extend(
                self._safe_list(
                    item.get(
                        key
                    )
                )
            )

        values.extend(
            self._safe_list(
                project_context.get(
                    "affected_modules",
                    []
                )
            )
        )

        return self._unique_strings(
            values
        )

    def _collect_evidence(
        self,
        item: dict[str, Any],
    ) -> list[str]:

        values: list[Any] = []

        for key in (
            "evidence",
            "examples",
            "occurrences",
            "traceback",
            "details",
        ):
            values.extend(
                self._safe_list(
                    item.get(
                        key
                    )
                )
            )

        return self._unique_strings(
            values
        )

    def _build_risks(
        self,
        improvement_type: str,
        severity: str,
        affected_files: list[str],
        affected_modules: list[str],
    ) -> list[str]:

        risks = [
            "Możliwość wprowadzenia regresji.",
            "Zmiana wymaga walidacji po wykonaniu.",
        ]

        if severity in {
            ImprovementSeverity.HIGH.value,
            ImprovementSeverity.CRITICAL.value,
        }:
            risks.append(
                "Wymagany jest backup i gotowy rollback."
            )

        if len(
            affected_files
        ) > 5:
            risks.append(
                "Zmiana obejmuje wiele plików."
            )

        if len(
            affected_modules
        ) > 2:
            risks.append(
                "Zmiana wpływa na wiele modułów."
            )

        if improvement_type == ImprovementType.SECURITY.value:
            risks.append(
                "Błędna zmiana może obniżyć bezpieczeństwo."
            )

        if improvement_type == ImprovementType.ARCHITECTURE.value:
            risks.append(
                "Zmiana architektury może wpływać na cały system."
            )

        return self._unique_strings(
            risks
        )

    def _build_benefits(
        self,
        improvement_type: str,
    ) -> list[str]:

        mapping = {
            ImprovementType.BUG_FIX.value: [
                "Usunięcie błędu.",
                "Poprawa stabilności.",
            ],
            ImprovementType.REFACTOR.value: [
                "Lepsza czytelność kodu.",
                "Łatwiejsze utrzymanie.",
            ],
            ImprovementType.PERFORMANCE.value: [
                "Szybsze działanie systemu.",
                "Mniejsze zużycie zasobów.",
            ],
            ImprovementType.SECURITY.value: [
                "Zmniejszenie ryzyka podatności.",
                "Lepsza ochrona danych.",
            ],
            ImprovementType.TESTING.value: [
                "Lepsze wykrywanie regresji.",
                "Większa pewność zmian.",
            ],
            ImprovementType.DOCUMENTATION.value: [
                "Łatwiejszy rozwój projektu.",
                "Lepsza wiedza o systemie.",
            ],
            ImprovementType.ARCHITECTURE.value: [
                "Lepsza modularność.",
                "Mniejsze sprzężenie komponentów.",
            ],
            ImprovementType.RELIABILITY.value: [
                "Większa odporność na błędy.",
                "Lepszy recovery i rollback.",
            ],
            ImprovementType.MAINTAINABILITY.value: [
                "Łatwiejsze rozwijanie kodu.",
                "Mniejszy koszt utrzymania.",
            ],
            ImprovementType.UNKNOWN.value: [
                "Potencjalna poprawa jakości projektu.",
            ],
        }

        return list(
            mapping.get(
                improvement_type,
                mapping[
                    ImprovementType.UNKNOWN.value
                ],
            )
        )

    def _build_recommended_actions(
        self,
        improvement_type: str,
    ) -> list[str]:

        common = [
            "Przeanalizować zależności.",
            "Przygotować bezpieczny patch.",
            "Uruchomić testy i walidację.",
        ]

        specialized = {
            ImprovementType.BUG_FIX.value: [
                "Odtworzyć problem.",
                "Zidentyfikować przyczynę źródłową.",
            ],
            ImprovementType.REFACTOR.value: [
                "Zachować istniejące zachowanie.",
                "Usunąć duplikację i uprościć strukturę.",
            ],
            ImprovementType.PERFORMANCE.value: [
                "Zmierz wydajność przed zmianą.",
                "Porównaj wyniki po optymalizacji.",
            ],
            ImprovementType.SECURITY.value: [
                "Zweryfikować model zagrożeń.",
                "Nie ujawniać sekretów i danych wrażliwych.",
            ],
            ImprovementType.TESTING.value: [
                "Dodać brakujące testy.",
                "Sprawdzić scenariusze regresyjne.",
            ],
            ImprovementType.DOCUMENTATION.value: [
                "Zaktualizować dokumentację i checkpoint.",
            ],
            ImprovementType.ARCHITECTURE.value: [
                "Zbudować graf wpływu zmian.",
                "Podzielić zmianę na małe etapy.",
            ],
            ImprovementType.RELIABILITY.value: [
                "Dodać recovery i retry.",
                "Zweryfikować rollback.",
            ],
            ImprovementType.MAINTAINABILITY.value: [
                "Uprościć nazwy i strukturę.",
                "Zmniejszyć złożoność kodu.",
            ],
            ImprovementType.UNKNOWN.value: [
                "Doprecyzować zakres ulepszenia.",
            ],
        }

        return self._unique_strings(
            specialized.get(
                improvement_type,
                specialized[
                    ImprovementType.UNKNOWN.value
                ],
            )
            + common
        )

    def _deduplicate_candidates(
        self,
        candidates: list[ImprovementCandidate],
    ) -> list[ImprovementCandidate]:

        result: list[
            ImprovementCandidate
        ] = []

        seen: set[
            tuple[str, str]
        ] = set()

        for candidate in candidates:
            key = (
                candidate.title.strip().lower(),
                candidate.improvement_type,
            )

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                candidate
            )

        return result

    def _extract_text(
        self,
        value: Any,
    ) -> str:

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        if isinstance(
            value,
            dict,
        ):
            texts: list[str] = []

            for key, item in value.items():
                if key in {
                    "raw",
                    "binary",
                    "content",
                }:
                    continue

                extracted = self._extract_text(
                    item
                )

                if extracted:
                    texts.append(
                        extracted
                    )

            return " ".join(
                texts
            )[:2000]

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
            ),
        ):
            return " ".join(
                self._extract_text(
                    item
                )
                for item in value
            )[:2000]

        if value is None:
            return ""

        return str(
            value
        )

    def _safe_float(
        self,
        value: Any,
        default: float,
    ) -> float:

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return default

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(
            value,
            list,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            set,
        ):
            return list(
                value
            )

        if value is None:
            return []

        return [
            value
        ]

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        return self._unique_strings(
            self._safe_list(
                value
            )
        )

    def _unique_strings(
        self,
        values: list[Any],
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            text = str(
                value
            ).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                text
            )

        return result
