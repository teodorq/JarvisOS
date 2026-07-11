from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class GoalType(str, Enum):
    CODE_IMPROVEMENT = "CODE_IMPROVEMENT"
    BUG_FIX = "BUG_FIX"
    REFACTOR = "REFACTOR"
    FEATURE = "FEATURE"
    RESEARCH = "RESEARCH"
    ANALYSIS = "ANALYSIS"
    QUESTION = "QUESTION"
    UNKNOWN = "UNKNOWN"


class GoalPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GoalComplexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class ReasoningGoal:
    original_request: str
    goal: str
    goal_type: str
    priority: str
    complexity: str
    requires_research: bool
    requires_developer: bool
    requires_confirmation: bool
    confidence: float
    keywords: list[str]
    detected_modules: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoalReasoner:

    GOAL_RULES = {
        GoalType.BUG_FIX: {
            "keywords": [
                "napraw",
                "naprawić",
                "naprawa",
                "błąd",
                "błędy",
                "bug",
                "error",
                "wyjątek",
                "exception",
                "nie działa",
                "nie uruchamia",
                "nie odpala",
                "zawiesza",
                "crash",
                "awaria",
                "problem",
                "popraw błąd",
            ],
            "weight": 1.4,
        },
        GoalType.REFACTOR: {
            "keywords": [
                "refaktor",
                "refaktoryzacja",
                "zrefaktoryzuj",
                "uporządkuj kod",
                "przebuduj kod",
                "uprość kod",
                "podziel klasę",
                "podziel moduł",
                "usuń duplikację",
                "clean code",
                "architektura",
            ],
            "weight": 1.3,
        },
        GoalType.FEATURE: {
            "keywords": [
                "dodaj",
                "utwórz",
                "zbuduj",
                "stwórz",
                "zaimplementuj",
                "nowa funkcja",
                "nowy moduł",
                "nową funkcję",
                "rozszerz",
                "integracja",
                "zintegruj",
                "obsługa",
            ],
            "weight": 1.2,
        },
        GoalType.RESEARCH: {
            "keywords": [
                "zbadaj",
                "research",
                "wyszukaj",
                "sprawdź dokumentację",
                "porównaj rozwiązania",
                "znajdź rozwiązanie",
                "przeanalizuj możliwości",
                "poszukaj informacji",
                "rozpoznaj temat",
            ],
            "weight": 1.2,
        },
        GoalType.ANALYSIS: {
            "keywords": [
                "przeanalizuj",
                "analiza",
                "sprawdź projekt",
                "sprawdź kod",
                "oceń kod",
                "wykryj problemy",
                "znajdź problemy",
                "przejrzyj",
                "zbadaj projekt",
                "audyt",
                "diagnostyka",
            ],
            "weight": 1.1,
        },
        GoalType.CODE_IMPROVEMENT: {
            "keywords": [
                "ulepsz",
                "popraw",
                "optymalizuj",
                "optymalizacja",
                "usprawnij",
                "przyspiesz",
                "zwiększ wydajność",
                "popraw jakość",
                "popraw bezpieczeństwo",
                "modernizuj",
            ],
            "weight": 1.0,
        },
        GoalType.QUESTION: {
            "keywords": [
                "jak",
                "czy",
                "dlaczego",
                "kiedy",
                "co",
                "gdzie",
                "który",
                "która",
                "które",
                "ile",
                "po co",
            ],
            "weight": 0.8,
        },
    }

    PRIORITY_RULES = {
        GoalPriority.CRITICAL: [
            "krytyczny",
            "pilne",
            "natychmiast",
            "awaria",
            "utrata danych",
            "bezpieczeństwo",
            "nie uruchamia się",
            "cały system nie działa",
            "rollback",
        ],
        GoalPriority.HIGH: [
            "ważne",
            "wysoki priorytet",
            "napraw",
            "błąd",
            "nie działa",
            "zawiesza",
            "crash",
            "blokuje",
            "problem",
        ],
        GoalPriority.MEDIUM: [
            "dodaj",
            "zbuduj",
            "utwórz",
            "ulepsz",
            "przeanalizuj",
            "refaktor",
            "optymalizuj",
        ],
        GoalPriority.LOW: [
            "później",
            "opcjonalnie",
            "drobna zmiana",
            "kosmetyczna",
            "kiedyś",
        ],
    }

    COMPLEXITY_RULES = {
        GoalComplexity.HIGH: [
            "cały projekt",
            "architektura",
            "przepisz",
            "przebuduj",
            "wiele modułów",
            "pełna integracja",
            "system",
            "core",
            "silnik",
            "self improvement",
            "multi-agent",
            "long term planner",
        ],
        GoalComplexity.MEDIUM: [
            "moduł",
            "klasa",
            "integracja",
            "refaktor",
            "workflow",
            "pipeline",
            "controller",
            "router",
            "service",
        ],
        GoalComplexity.LOW: [
            "jedna funkcja",
            "pojedyncza funkcja",
            "literówka",
            "komunikat",
            "nazwa",
            "mała zmiana",
            "drobna zmiana",
        ],
    }

    MODULE_ALIASES = {
        "vision": [
            "vision",
            "screenvision",
            "visionai",
            "visionagent",
            "visionbrain",
            "visionmemory",
            "guidetector",
            "screenanalyzer",
            "contextdetector",
        ],
        "autodev": [
            "autodev",
            "developercontroller",
            "patch generator",
            "patch preview",
            "rollback",
            "developer executor",
            "developer validator",
        ],
        "research": [
            "research",
            "researchagent",
            "researchcontroller",
            "researchworkflow",
            "researchpipeline",
            "researchservice",
        ],
        "brain": [
            "brain",
            "plannerllm",
            "cognitiveengine",
            "researchrouter",
            "autodevrouter",
        ],
        "memory": [
            "memory",
            "pamięć",
            "reasoningmemory",
            "researchmemory",
            "visionmemory",
        ],
        "desktop": [
            "desktop",
            "desktopcontroller",
            "commandexecutor",
            "pyautogui",
        ],
        "browser": [
            "browser",
            "browseragent",
            "youtube",
            "google",
            "chrome",
            "opera",
        ],
        "voice": [
            "voice",
            "głos",
            "voicelistener",
            "mikrofon",
        ],
        "ui": [
            "ui",
            "mainwindow",
            "pyside",
            "dashboard",
            "interfejs",
        ],
        "reasoner": [
            "reasoner",
            "goalreasoner",
            "decisiongraph",
            "optiongenerator",
            "riskevaluator",
            "strategybuilder",
        ],
    }

    RESEARCH_REQUIRED_TYPES = {
        GoalType.RESEARCH,
        GoalType.ANALYSIS,
        GoalType.CODE_IMPROVEMENT,
        GoalType.REFACTOR,
    }

    DEVELOPER_REQUIRED_TYPES = {
        GoalType.BUG_FIX,
        GoalType.REFACTOR,
        GoalType.FEATURE,
        GoalType.CODE_IMPROVEMENT,
    }

    CONFIRMATION_REQUIRED_TYPES = {
        GoalType.BUG_FIX,
        GoalType.REFACTOR,
        GoalType.FEATURE,
        GoalType.CODE_IMPROVEMENT,
    }

    STOP_WORDS = {
        "a",
        "aby",
        "ale",
        "bo",
        "by",
        "czy",
        "dla",
        "do",
        "i",
        "jak",
        "jest",
        "lub",
        "mi",
        "na",
        "nie",
        "o",
        "od",
        "oraz",
        "po",
        "pod",
        "się",
        "to",
        "w",
        "we",
        "z",
        "za",
        "ze",
        "ten",
        "ta",
        "te",
        "tym",
        "tego",
        "proszę",
        "jarvis",
    }

    def reason(self, user_request: str) -> dict[str, Any]:
        normalized_request = self._normalize_text(user_request)

        if not normalized_request:
            return self._build_unknown_goal(user_request).to_dict()

        goal_type, confidence, scores = self._detect_goal_type(
            normalized_request
        )

        priority = self._detect_priority(
            normalized_request,
            goal_type,
        )

        complexity = self._detect_complexity(
            normalized_request,
            goal_type,
        )

        detected_modules = self._detect_modules(
            normalized_request
        )

        keywords = self._extract_keywords(
            normalized_request
        )

        goal_description = self._build_goal_description(
            user_request=user_request,
            goal_type=goal_type,
            detected_modules=detected_modules,
        )

        requires_research = self._requires_research(
            goal_type=goal_type,
            complexity=complexity,
            detected_modules=detected_modules,
        )

        requires_developer = (
            goal_type in self.DEVELOPER_REQUIRED_TYPES
        )

        requires_confirmation = (
            goal_type in self.CONFIRMATION_REQUIRED_TYPES
        )

        result = ReasoningGoal(
            original_request=user_request.strip(),
            goal=goal_description,
            goal_type=goal_type.value,
            priority=priority.value,
            complexity=complexity.value,
            requires_research=requires_research,
            requires_developer=requires_developer,
            requires_confirmation=requires_confirmation,
            confidence=round(confidence, 2),
            keywords=keywords,
            detected_modules=detected_modules,
            metadata={
                "classification_scores": scores,
                "reasoner_version": "1.0.0",
                "normalized_request": normalized_request,
            },
        )

        return result.to_dict()

    def analyze(self, user_request: str) -> dict[str, Any]:
        return self.reason(user_request)

    def build_goal(self, user_request: str) -> dict[str, Any]:
        return self.reason(user_request)

    def _detect_goal_type(
        self,
        text: str,
    ) -> tuple[GoalType, float, dict[str, float]]:

        scores: dict[GoalType, float] = {
            goal_type: 0.0
            for goal_type in GoalType
        }

        for goal_type, config in self.GOAL_RULES.items():
            weight = float(config["weight"])
            keywords = config["keywords"]

            for keyword in keywords:
                if self._contains_phrase(text, keyword):
                    scores[goal_type] += weight

                    if text.startswith(keyword):
                        scores[goal_type] += 0.25

        if text.endswith("?"):
            scores[GoalType.QUESTION] += 0.8

        if self._looks_like_question(text):
            scores[GoalType.QUESTION] += 0.4

        if (
            scores[GoalType.BUG_FIX] > 0
            and scores[GoalType.CODE_IMPROVEMENT] > 0
        ):
            scores[GoalType.BUG_FIX] += 0.35

        if (
            scores[GoalType.FEATURE] > 0
            and scores[GoalType.RESEARCH] > 0
        ):
            scores[GoalType.FEATURE] += 0.15

        best_goal_type = max(
            scores,
            key=scores.get,
        )

        best_score = scores[best_goal_type]

        if best_score <= 0:
            best_goal_type = GoalType.UNKNOWN
            confidence = 0.25
        else:
            total_score = sum(scores.values())

            if total_score <= 0:
                confidence = 0.5
            else:
                confidence = min(
                    0.99,
                    0.55 + (
                        best_score / total_score
                    ) * 0.44,
                )

        serialized_scores = {
            goal_type.value: round(score, 2)
            for goal_type, score in scores.items()
            if score > 0
        }

        return (
            best_goal_type,
            confidence,
            serialized_scores,
        )

    def _detect_priority(
        self,
        text: str,
        goal_type: GoalType,
    ) -> GoalPriority:

        for priority in [
            GoalPriority.CRITICAL,
            GoalPriority.HIGH,
            GoalPriority.LOW,
        ]:
            keywords = self.PRIORITY_RULES[priority]

            if any(
                self._contains_phrase(text, keyword)
                for keyword in keywords
            ):
                return priority

        if goal_type == GoalType.BUG_FIX:
            return GoalPriority.HIGH

        if goal_type in {
            GoalType.REFACTOR,
            GoalType.FEATURE,
            GoalType.CODE_IMPROVEMENT,
        }:
            return GoalPriority.MEDIUM

        if goal_type in {
            GoalType.RESEARCH,
            GoalType.ANALYSIS,
            GoalType.QUESTION,
        }:
            return GoalPriority.MEDIUM

        return GoalPriority.LOW

    def _detect_complexity(
        self,
        text: str,
        goal_type: GoalType,
    ) -> GoalComplexity:

        for complexity in [
            GoalComplexity.HIGH,
            GoalComplexity.LOW,
        ]:
            keywords = self.COMPLEXITY_RULES[complexity]

            if any(
                self._contains_phrase(text, keyword)
                for keyword in keywords
            ):
                return complexity

        medium_keywords = self.COMPLEXITY_RULES[
            GoalComplexity.MEDIUM
        ]

        if any(
            self._contains_phrase(text, keyword)
            for keyword in medium_keywords
        ):
            return GoalComplexity.MEDIUM

        word_count = len(text.split())

        if word_count >= 20:
            return GoalComplexity.HIGH

        if word_count >= 8:
            return GoalComplexity.MEDIUM

        if goal_type in {
            GoalType.REFACTOR,
            GoalType.CODE_IMPROVEMENT,
        }:
            return GoalComplexity.MEDIUM

        return GoalComplexity.LOW

    def _detect_modules(
        self,
        text: str,
    ) -> list[str]:

        detected_modules: list[str] = []

        for module_name, aliases in self.MODULE_ALIASES.items():
            if any(
                self._contains_phrase(text, alias)
                for alias in aliases
            ):
                detected_modules.append(module_name)

        return detected_modules

    def _extract_keywords(
        self,
        text: str,
        limit: int = 12,
    ) -> list[str]:

        words = re.findall(
            r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_]+",
            text.lower(),
        )

        keywords: list[str] = []

        for word in words:
            if len(word) < 3:
                continue

            if word in self.STOP_WORDS:
                continue

            if word not in keywords:
                keywords.append(word)

            if len(keywords) >= limit:
                break

        return keywords

    def _build_goal_description(
        self,
        user_request: str,
        goal_type: GoalType,
        detected_modules: list[str],
    ) -> str:

        cleaned_request = user_request.strip()

        module_text = ""

        if detected_modules:
            module_text = ", ".join(detected_modules)

        prefixes = {
            GoalType.BUG_FIX: "Naprawić problem",
            GoalType.REFACTOR: "Zrefaktoryzować kod",
            GoalType.FEATURE: "Zaimplementować nową funkcjonalność",
            GoalType.RESEARCH: "Przeprowadzić research",
            GoalType.ANALYSIS: "Przeanalizować projekt",
            GoalType.CODE_IMPROVEMENT: "Ulepszyć kod projektu",
            GoalType.QUESTION: "Odpowiedzieć na pytanie użytkownika",
            GoalType.UNKNOWN: "Rozpoznać i obsłużyć cel użytkownika",
        }

        prefix = prefixes[goal_type]

        if module_text:
            return (
                f"{prefix} w obszarze: {module_text}. "
                f"Polecenie: {cleaned_request}"
            )

        return f"{prefix}. Polecenie: {cleaned_request}"

    def _requires_research(
        self,
        goal_type: GoalType,
        complexity: GoalComplexity,
        detected_modules: list[str],
    ) -> bool:

        if goal_type in self.RESEARCH_REQUIRED_TYPES:
            return True

        if (
            goal_type == GoalType.FEATURE
            and complexity in {
                GoalComplexity.MEDIUM,
                GoalComplexity.HIGH,
            }
        ):
            return True

        if (
            goal_type == GoalType.BUG_FIX
            and complexity == GoalComplexity.HIGH
        ):
            return True

        if len(detected_modules) >= 2:
            return True

        return False

    def _looks_like_question(
        self,
        text: str,
    ) -> bool:

        question_starters = (
            "jak ",
            "czy ",
            "dlaczego ",
            "kiedy ",
            "co ",
            "gdzie ",
            "który ",
            "która ",
            "które ",
            "ile ",
            "po co ",
        )

        return text.startswith(question_starters)

    def _contains_phrase(
        self,
        text: str,
        phrase: str,
    ) -> bool:

        normalized_phrase = self._normalize_text(phrase)

        if " " in normalized_phrase:
            return normalized_phrase in text

        pattern = (
            r"(?<![a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_])"
            + re.escape(normalized_phrase)
            + r"(?![a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ0-9_])"
        )

        return re.search(pattern, text) is not None

    def _normalize_text(
        self,
        text: str,
    ) -> str:

        if not isinstance(text, str):
            return ""

        normalized = text.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)

        return normalized

    def _build_unknown_goal(
        self,
        user_request: str,
    ) -> ReasoningGoal:

        original_request = (
            user_request.strip()
            if isinstance(user_request, str)
            else ""
        )

        return ReasoningGoal(
            original_request=original_request,
            goal="Rozpoznać niepuste polecenie użytkownika.",
            goal_type=GoalType.UNKNOWN.value,
            priority=GoalPriority.LOW.value,
            complexity=GoalComplexity.LOW.value,
            requires_research=False,
            requires_developer=False,
            requires_confirmation=False,
            confidence=0.0,
            keywords=[],
            detected_modules=[],
            metadata={
                "classification_scores": {},
                "reasoner_version": "1.0.0",
                "normalized_request": "",
            },
        )