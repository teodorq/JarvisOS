from dataclasses import dataclass, field
from typing import Any

from app.autodev.research_query import (
    ResearchQuery
)
from app.autodev.research_task import (
    ResearchTask
)


@dataclass
class GoalMappingResult:

    goal: str

    category: str = "general"

    keywords: list[str] = field(
        default_factory=list
    )

    queries: list[
        ResearchQuery
    ] = field(
        default_factory=list
    )

    tasks: list[
        ResearchTask
    ] = field(
        default_factory=list
    )

    confidence: float = 0.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def add_keyword(
        self,
        keyword: str
    ):

        keyword = keyword.strip()

        if (
            keyword
            and keyword not in self.keywords
        ):
            self.keywords.append(
                keyword
            )

    def add_query(
        self,
        query: ResearchQuery
    ):

        self.queries.append(
            query
        )

    def add_task(
        self,
        task: ResearchTask
    ):

        self.tasks.append(
            task
        )

    def summary(
        self
    ) -> str:

        lines = [
            "GOAL MAPPING RESULT",
            f"Cel: {self.goal}",
            f"Kategoria: {self.category}",
            f"Confidence: {self.confidence:.2f}",
            f"Keywords: {len(self.keywords)}",
            f"Queries: {len(self.queries)}",
            f"Tasks: {len(self.tasks)}"
        ]

        if self.keywords:
            lines.append("")
            lines.append("Słowa kluczowe:")

            for keyword in self.keywords:
                lines.append(
                    f"- {keyword}"
                )

        if self.queries:
            lines.append("")
            lines.append("Zapytania:")

            for query in self.queries:
                lines.append(
                    f"- {query.goal}"
                )

        if self.tasks:
            lines.append("")
            lines.append("Zadania:")

            for task in self.tasks:
                lines.append(
                    f"- P{task.priority} "
                    f"{task.title}"
                )

        return "\n".join(
            lines
        )


class ResearchGoalMapper:

    CATEGORY_KEYWORDS = {
        "vision": [
            "vision",
            "ekran",
            "screen",
            "obraz",
            "gui",
            "detector",
            "youtube",
            "klik",
            "rozpoznawanie"
        ],
        "brain": [
            "brain",
            "planner",
            "planer",
            "reasoner",
            "myślenie",
            "myslenie",
            "decyzja",
            "polecenie"
        ],
        "memory": [
            "memory",
            "pamięć",
            "pamiec",
            "historia",
            "zapamiętaj",
            "zapamietaj"
        ],
        "voice": [
            "voice",
            "głos",
            "glos",
            "mikrofon",
            "mowa",
            "rozmowa"
        ],
        "browser": [
            "browser",
            "przeglądarka",
            "przegladarka",
            "opera",
            "chrome",
            "google",
            "youtube"
        ],
        "desktop": [
            "desktop",
            "pulpit",
            "okno",
            "mysz",
            "klawiatura",
            "aplikacja"
        ],
        "autodev": [
            "autodev",
            "developer",
            "patch",
            "refaktor",
            "refaktoryzacja",
            "kod",
            "projekt"
        ],
        "gui": [
            "gui",
            "interfejs",
            "okno",
            "dashboard",
            "przycisk"
        ]
    }

    ACTION_WORDS = {
        "analyze": [
            "przeanalizuj",
            "sprawdź",
            "sprawdz",
            "zbadaj",
            "oceń",
            "ocen"
        ],
        "improve": [
            "popraw",
            "ulepsz",
            "usprawnij",
            "zoptymalizuj"
        ],
        "refactor": [
            "refaktoryzuj",
            "refaktoryzacja",
            "przebuduj",
            "podziel"
        ],
        "find": [
            "znajdź",
            "znajdz",
            "wyszukaj",
            "pokaż",
            "pokaz"
        ]
    }

    def map_goal(
        self,
        goal: str
    ) -> GoalMappingResult:

        normalized = (
            goal.lower().strip()
        )

        result = GoalMappingResult(
            goal=goal
        )

        result.category = (
            self._detect_category(
                normalized
            )
        )

        action_type = (
            self._detect_action(
                normalized
            )
        )

        extracted_keywords = (
            self._extract_keywords(
                normalized,
                result.category
            )
        )

        for keyword in extracted_keywords:
            result.add_keyword(
                keyword
            )

        main_query = ResearchQuery(
            goal=goal,
            keywords=list(
                result.keywords
            ),
            categories=(
                [result.category]
                if result.category != "general"
                else []
            ),
            max_results=50,
            metadata={
                "source": (
                    "research_goal_mapper"
                ),
                "action_type": action_type
            }
        )

        result.add_query(
            main_query
        )

        if result.category != "general":
            dependency_query = (
                ResearchQuery(
                    goal=(
                        "Znajdź zależności "
                        f"modułu {result.category}"
                    ),
                    keywords=[
                        result.category
                    ],
                    categories=[
                        result.category
                    ],
                    max_results=30,
                    metadata={
                        "source": (
                            "research_goal_mapper"
                        ),
                        "query_type": (
                            "dependencies"
                        )
                    }
                )
            )

            result.add_query(
                dependency_query
            )

        if action_type in {
            "improve",
            "refactor"
        }:
            quality_query = (
                ResearchQuery(
                    goal=(
                        "Wykryj problemy jakości "
                        f"dla {result.category}"
                    ),
                    keywords=list(
                        result.keywords
                    ),
                    categories=(
                        [result.category]
                        if result.category != "general"
                        else []
                    ),
                    max_results=40,
                    metadata={
                        "source": (
                            "research_goal_mapper"
                        ),
                        "query_type": (
                            "quality_analysis"
                        )
                    }
                )
            )

            result.add_query(
                quality_query
            )

        result.tasks = (
            self._build_initial_tasks(
                goal=goal,
                category=result.category,
                action_type=action_type
            )
        )

        result.confidence = (
            self._calculate_confidence(
                category=result.category,
                keywords=result.keywords,
                action_type=action_type
            )
        )

        result.metadata[
            "action_type"
        ] = action_type

        result.metadata[
            "normalized_goal"
        ] = normalized

        return result

    def _detect_category(
        self,
        goal: str
    ) -> str:

        scores = {}

        for category, keywords in (
            self.CATEGORY_KEYWORDS.items()
        ):
            score = 0

            for keyword in keywords:
                if keyword in goal:
                    score += 1

            scores[
                category
            ] = score

        if not scores:
            return "general"

        best_category = max(
            scores,
            key=scores.get
        )

        if scores[
            best_category
        ] == 0:
            return "general"

        return best_category

    def _detect_action(
        self,
        goal: str
    ) -> str:

        for action_type, words in (
            self.ACTION_WORDS.items()
        ):
            for word in words:
                if word in goal:
                    return action_type

        return "analyze"

    def _extract_keywords(
        self,
        goal: str,
        category: str
    ) -> list[str]:

        stop_words = {
            "jarvis",
            "proszę",
            "prosze",
            "moduł",
            "modul",
            "projekt",
            "oraz",
            "który",
            "ktory",
            "jest",
            "dla",
            "ten",
            "ta",
            "to",
            "i",
            "w",
            "z",
            "na",
            "do"
        }

        action_words = set()

        for words in (
            self.ACTION_WORDS.values()
        ):
            action_words.update(
                words
            )

        cleaned = (
            goal.replace(",", " ")
            .replace(".", " ")
            .replace(":", " ")
            .replace(";", " ")
            .replace("-", " ")
        )

        words = [
            word.strip()
            for word in cleaned.split()
            if word.strip()
        ]

        keywords = []

        if category != "general":
            keywords.append(
                category
            )

        for word in words:
            if len(word) < 3:
                continue

            if word in stop_words:
                continue

            if word in action_words:
                continue

            if word not in keywords:
                keywords.append(
                    word
                )

        return keywords[:15]

    def _build_initial_tasks(
        self,
        goal: str,
        category: str,
        action_type: str
    ) -> list[ResearchTask]:

        tasks = []

        analysis_task = ResearchTask(
            title=(
                "Przeanalizuj strukturę "
                f"obszaru {category}"
            ),
            target=category,
            description=goal,
            task_type="analysis",
            priority=1,
            estimated_risk="LOW",
            estimated_time=10,
            requires_backup=False,
            requires_validation=False,
            requires_approval=False
        )

        analysis_task.add_action(
            "Uruchom ProjectScanner."
        )

        analysis_task.add_action(
            "Zbuduj KnowledgeGraph."
        )

        analysis_task.add_action(
            "Wykonaj SemanticSearch."
        )

        tasks.append(
            analysis_task
        )

        dependency_task = ResearchTask(
            title=(
                "Sprawdź zależności "
                f"obszaru {category}"
            ),
            target=category,
            description=(
                "Znajdź moduły zależne "
                "i oceniaj wpływ zmian."
            ),
            task_type="dependency_analysis",
            priority=2,
            estimated_risk="LOW",
            estimated_time=10,
            requires_backup=False,
            requires_validation=False,
            requires_approval=False
        )

        dependency_task.add_action(
            "Przeanalizuj importy."
        )

        dependency_task.add_action(
            "Znajdź moduły używające targetu."
        )

        tasks.append(
            dependency_task
        )

        if action_type in {
            "improve",
            "refactor"
        }:
            improvement_task = ResearchTask(
                title=(
                    "Przygotuj plan poprawy "
                    f"obszaru {category}"
                ),
                target=category,
                description=goal,
                task_type="refactor",
                priority=3,
                estimated_risk="MEDIUM",
                estimated_time=20,
                requires_backup=True,
                requires_validation=True,
                requires_approval=True
            )

            improvement_task.add_action(
                "Wykryj problemy jakości."
            )

            improvement_task.add_action(
                "Wygeneruj sugestie zmian."
            )

            improvement_task.add_action(
                "Przygotuj ResearchPlan."
            )

            tasks.append(
                improvement_task
            )

        return tasks

    def _calculate_confidence(
        self,
        category: str,
        keywords: list[str],
        action_type: str
    ) -> float:

        confidence = 0.40

        if category != "general":
            confidence += 0.25

        if keywords:
            confidence += min(
                len(keywords) * 0.03,
                0.20
            )

        if action_type != "analyze":
            confidence += 0.10

        return min(
            confidence,
            0.95
        )