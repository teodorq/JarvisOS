"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import ast
import json
import re
from pathlib import Path
from typing import Any

from app.autodev.change_impact import ChangeImpactAnalyzer
from app.autodev.dependency_graph import DependencyGraph
from app.autodev.developer_loop import DeveloperLoop
from app.autodev.developer_agent_proposal_service import (
    DeveloperAgentProposalService,
)
from app.autodev.llm_patch_generator import (
    LLMPatchGenerator,
    LLMPatchRequest,
)
from app.ai.llm import LocalLLM


_DEVELOPER_AGENT_PROPOSALS = DeveloperAgentProposalService()


class LocalLLMPatchModel:

    def __init__(
        self,
        llm: LocalLLM | None = None,
    ) -> None:
        self.llm = llm or LocalLLM()

    def generate_patch(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        prompt = self._build_prompt(
            payload
        )
        response = self.llm.ask(
            prompt
        )

        if not response:
            return {
                "proposed_content": "",
                "explanation": "",
                "warnings": [
                    "Model zwrócił pustą odpowiedź."
                ],
            }

        if response.startswith(
            "BŁĄD"
        ):
            raise RuntimeError(
                response
            )

        parsed = self._parse_response(
            response
        )

        if parsed:
            return parsed

        return {
            "proposed_content": "",
            "explanation": response,
            "warnings": [
                (
                    "Nie udało się odczytać "
                    "proponowanego kodu z odpowiedzi LLM."
                )
            ],
        }

    @staticmethod
    def _build_prompt(
        payload: dict[str, Any],
    ) -> str:

        goal = str(
            payload.get(
                "goal",
                "",
            )
        )
        path = str(
            payload.get(
                "path",
                "",
            )
        )
        issue_type = str(
            payload.get(
                "issue_type",
                "",
            )
        )
        strategy = str(
            payload.get(
                "strategy",
                "",
            )
        )
        source = str(
            payload.get(
                "source_content",
                "",
            )
        )
        constraints = [
            str(item)
            for item in payload.get(
                "constraints",
                [],
            )
        ]

        return (
            "Jesteś bezpiecznym generatorem zmian "
            "dla projektu JARVIS OS.\n"
            "Zwróć WYŁĄCZNIE poprawny JSON bez markdownu "
            "w formacie:\n"
            "{"
            "\"proposed_content\": \"pełna zawartość pliku\", "
            "\"explanation\": \"krótkie wyjaśnienie\", "
            "\"warnings\": []"
            "}\n\n"
            f"Plik: {path}\n"
            f"Cel: {goal}\n"
            f"Typ problemu: {issue_type}\n"
            f"Strategia: {strategy}\n"
            f"Ograniczenia: {constraints}\n\n"
            "Zasady:\n"
            "- zwróć PEŁNĄ zawartość pliku, nie diff;\n"
            "- zachowaj obecne funkcje, chyba że cel wymaga zmiany;\n"
            "- nie dodawaj kodu sieciowego, destrukcyjnego ani "
            "omijającego zabezpieczenia;\n"
            "- kod musi mieć poprawną składnię Python;\n"
            "- wykonaj najmniejszą bezpieczną zmianę.\n\n"
            "AKTUALNA ZAWARTOŚĆ PLIKU:\n"
            f"{source}"
        )

    @staticmethod
    def _parse_response(
        response: str,
    ) -> dict[str, Any]:

        text = response.strip()

        fenced_json = re.search(
            r"```(?:json)?\s*([\s\S]*?)```",
            text,
            re.IGNORECASE,
        )

        candidates = [
            (
                fenced_json.group(1).strip()
                if fenced_json
                else ""
            ),
            text,
        ]

        first_brace = text.find(
            "{"
        )
        last_brace = text.rfind(
            "}"
        )

        if (
            first_brace >= 0
            and last_brace > first_brace
        ):
            candidates.append(
                text[
                    first_brace:last_brace + 1
                ]
            )

        for candidate in candidates:
            if not candidate:
                continue

            try:
                value = json.loads(
                    candidate
                )
            except json.JSONDecodeError:
                continue

            if not isinstance(
                value,
                dict,
            ):
                continue

            proposed = str(
                value.get(
                    "proposed_content",
                    value.get(
                        "new_content",
                        "",
                    ),
                )
            )

            if proposed:
                return {
                    "proposed_content": proposed,
                    "explanation": str(
                        value.get(
                            "explanation",
                            "",
                        )
                    ),
                    "warnings": [
                        str(item)
                        for item in value.get(
                            "warnings",
                            [],
                        )
                    ],
                }

        fenced_code = re.search(
            r"```(?:python|py)?\s*([\s\S]*?)```",
            text,
            re.IGNORECASE,
        )

        if fenced_code:
            proposed = fenced_code.group(
                1
            ).strip()

            if proposed:
                return {
                    "proposed_content": (
                        proposed + "\n"
                    ),
                    "explanation": (
                        "Kod odczytany z bloku odpowiedzi LLM."
                    ),
                    "warnings": [],
                }

        return {}


class DeveloperAgent:

    def __init__(
        self,
        project_root: str = default_project_root(),
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()
        self.graph = DependencyGraph()
        self.impact = ChangeImpactAnalyzer()
        self.loop = DeveloperLoop()
        self.llm_patch_generator = (
            LLMPatchGenerator(
                model=LocalLLMPatchModel()
            )
        )

    def build_dependency_graph(self) -> str:
        self.graph.build()
        return self.graph.summary_text()

    def analyze_symbol_impact(
        self,
        symbol_name: str,
    ):
        return self.impact.analyze_symbol(
            symbol_name
        )

    def analyze_module_impact(
        self,
        module_name: str,
    ):
        return self.impact.analyze_module(
            module_name
        )

    def plan_symbol_change(
        self,
        symbol_name: str,
    ) -> str:

        if not self.graph.files:
            self.graph.build()

        impact = self.graph.impact_for_symbol(
            symbol_name
        )

        files = impact.get("files", [])
        references_count = impact.get(
            "references_count",
            0,
        )

        lines = [
            "AUTODEV CHANGE PLAN",
            f"Cel: zmiana symbolu {symbol_name}",
            f"Pliki zależne: {len(files)}",
            f"Referencje: {references_count}",
            "",
            "Plan:",
            "1. Utworzyć backup zmienianych plików.",
            f"2. Zmodyfikować symbol: {symbol_name}.",
            "3. Sprawdzić pliki zależne.",
            "4. Uruchomić test importów.",
            "5. Uruchomić kontrolę składni.",
            "6. Cofnąć zmiany, jeśli test nie przejdzie.",
        ]

        if files:
            lines.append("")
            lines.append("Pliki do sprawdzenia:")

            for path in files[:30]:
                lines.append(f"- {path}")

        return "\n".join(lines)

    def prepare_developer_task(
        self,
        goal_text: str,
        target: str,
    ) -> str:

        return self.loop.prepare(
            goal_text=goal_text,
            target=target,
        )

    def prepare_planned_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return _DEVELOPER_AGENT_PROPOSALS.prepare_planned_task(self, task)


    def generate_code_proposal(self, *, target: str, goal: str, task: dict[str, Any] | None=None) -> dict[str, Any]:
        return _DEVELOPER_AGENT_PROPOSALS.generate_code_proposal(self, target=target, goal=goal, task=task)


    def review_code_proposal(self, *, source_content: str, proposed_content: str, file_path: Path) -> dict[str, Any]:
        return _DEVELOPER_AGENT_PROPOSALS.review_code_proposal(self, source_content=source_content, proposed_content=proposed_content, file_path=file_path)


    def _retry_after_review(self, *, file_path: Path, goal: str, source_content: str, proposal: str, review: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        return _DEVELOPER_AGENT_PROPOSALS._retry_after_review(self, file_path=file_path, goal=goal, source_content=source_content, proposal=proposal, review=review, task=task)


    @classmethod
    def _bootstrap_new_python_file(
        cls,
        *,
        goal: str,
        title: str,
        file_path: Path,
    ) -> str:

        combined = (
            f"{title} {goal}"
        ).strip()

        function_name = cls._requested_function_name(
            combined
        )

        if function_name:
            return (
                "from __future__ import annotations\n\n"
                f'"""Moduł zawierający funkcję '
                f'{function_name}."""\n\n\n'
                f"def {function_name}() -> None:\n"
                f'    """Bezpieczny szkielet funkcji '
                f'{function_name}."""\n\n'
                "    return None\n"
            )

        class_name = cls._requested_class_name(
            combined
        )

        if class_name:
            return (
                "from __future__ import annotations\n\n"
                f'"""Moduł zawierający klasę '
                f'{class_name}."""\n\n\n'
                f"class {class_name}:\n"
                f'    """Bezpieczny szkielet klasy '
                f'{class_name}."""\n\n'
                "    pass\n"
            )

        fallback_name = cls._safe_identifier(
            file_path.stem
        )
        class_name = "".join(
            part.capitalize()
            for part in fallback_name.split(
                "_"
            )
            if part
        ) or "GeneratedFeature"

        return (
            "from __future__ import annotations\n\n"
            f'"""Autonomicznie utworzony moduł '
            f'{file_path.stem}."""\n\n\n'
            f"class {class_name}:\n"
            f'    """Bezpieczny szkielet funkcjonalności."""\n\n'
            "    pass\n"
        )

    @classmethod
    def _requested_class_name(
        cls,
        text: str,
    ) -> str:

        match = re.search(
            r"(?:class|klas(?:a|ę|e|y|ą))\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)",
            str(text),
            re.IGNORECASE,
        )

        if not match:
            return ""

        candidate = match.group(1)

        if not candidate.isidentifier():
            return ""

        return candidate

    @classmethod
    def _requested_function_name(
        cls,
        text: str,
    ) -> str:

        match = re.search(
            r"(?:function|funkcj(?:a|ę|e|i|ą))\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)",
            str(text),
            re.IGNORECASE,
        )

        if not match:
            return ""

        return cls._safe_identifier(
            match.group(1)
        )

    @staticmethod
    def _safe_identifier(
        value: str,
    ) -> str:

        normalized = re.sub(
            r"[^A-Za-z0-9_]+",
            "_",
            str(value),
        ).strip(
            "_"
        )

        if not normalized:
            return "generated_feature"

        if normalized[0].isdigit():
            normalized = (
                "generated_"
                + normalized
            )

        return normalized

    def _proposal_for_task(self, *, source: str, tree: ast.AST, title: str, metadata: dict[str, Any]) -> tuple[str, str]:
        return _DEVELOPER_AGENT_PROPOSALS._proposal_for_task(self, source=source, tree=tree, title=title, metadata=metadata)


    def _resolve_target(
        self,
        target: str,
    ) -> Path:

        path = Path(
            str(target)
        )

        if not path.is_absolute():
            path = self.project_root / path

        return path.resolve()

    def _is_safe_target(
        self,
        path: Path,
    ) -> bool:

        try:
            relative = path.relative_to(
                self.project_root
            )
        except ValueError:
            return False

        normalized = str(
            relative
        ).replace(
            "\\",
            "/",
        ).casefold()

        protected = (
            ".git/",
            ".venv/",
            "archive/",
            "backups/",
            "data/backups/",
            "ai_pliki/",
        )

        return not any(
            normalized.startswith(
                item
            )
            for item in protected
        )

    @staticmethod
    def _has_future_annotations(
        tree: ast.AST,
    ) -> bool:

        return any(
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module == "__future__"
            and any(
                alias.name == "annotations"
                for alias in node.names
            )
            for node in getattr(
                tree,
                "body",
                [],
            )
        )

    @staticmethod
    def _add_module_docstring(
        source: str,
        tree: ast.AST,
    ) -> str:

        lines = source.splitlines(
            keepends=True
        )
        insert_index = 0

        if lines and lines[0].startswith(
            "#!"
        ):
            insert_index = 1

        future_imports = [
            node
            for node in getattr(
                tree,
                "body",
                [],
            )
            if isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module == "__future__"
        ]

        if future_imports:
            insert_index = max(
                int(
                    getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    )
                )
                for node in future_imports
            )

        lines.insert(
            insert_index,
            (
                '"""Moduł JARVIS OS zarządzany '
                'przez bezpieczny AutoDev."""\n\n'
            ),
        )

        return "".join(
            lines
        )

    @staticmethod
    def _add_future_annotations(
        source: str,
        tree: ast.AST,
    ) -> str:

        lines = source.splitlines(
            keepends=True
        )
        insert_index = 0

        if lines and lines[0].startswith(
            "#!"
        ):
            insert_index = 1

        body = getattr(
            tree,
            "body",
            [],
        )

        if body:
            first = body[0]

            if (
                isinstance(
                    first,
                    ast.Expr,
                )
                and isinstance(
                    getattr(
                        first,
                        "value",
                        None,
                    ),
                    ast.Constant,
                )
                and isinstance(
                    first.value.value,
                    str,
                )
            ):
                insert_index = int(
                    getattr(
                        first,
                        "end_lineno",
                        first.lineno,
                    )
                )

        lines.insert(
            insert_index,
            "from __future__ import annotations\n\n",
        )

        return "".join(
            lines
        )

    @staticmethod
    def _normalize_task_comment(
        source: str,
        line_number: int,
    ) -> str:

        lines = source.splitlines(
            keepends=True
        )

        index = line_number - 1

        if not (
            0 <= index < len(lines)
        ):
            return source

        original = lines[index]
        stripped = original.lstrip()
        indentation = original[
            :len(original) - len(stripped)
        ]

        if not stripped.startswith(
            "#"
        ):
            return source

        content = stripped.lstrip(
            "#"
        ).strip()

        for keyword in (
            "TODO",
            "FIXME",
            "XXX",
            "HACK",
        ):
            if content.upper().startswith(
                keyword
            ):
                content = content[
                    len(keyword):
                ].lstrip(
                    ": -"
                )
                break

        replacement = (
            indentation
            + "# AutoDev task: "
            + (
                content
                or "wymaga dalszej analizy"
            )
        )

        if original.endswith(
            "\n"
        ):
            replacement += "\n"

        lines[index] = replacement
        return "".join(
            lines
        )

    @staticmethod
    def _replace_empty_except(
        source: str,
        tree: ast.AST,
        line_number: int,
    ) -> str:

        target = None

        for node in ast.walk(
            tree
        ):
            if not isinstance(
                node,
                ast.ExceptHandler,
            ):
                continue

            if (
                line_number > 0
                and node.lineno != line_number
            ):
                continue

            if (
                len(node.body) == 1
                and isinstance(
                    node.body[0],
                    ast.Pass,
                )
            ):
                target = node.body[0]
                break

        if target is None:
            return source

        lines = source.splitlines(
            keepends=True
        )
        index = target.lineno - 1

        if not (
            0 <= index < len(lines)
        ):
            return source

        original = lines[index]
        indentation = original[
            :len(original) - len(original.lstrip())
        ]
        replacement = (
            indentation
            + 'raise RuntimeError('
            + '"AutoDev: przechwycony wyjątek")'
        )

        if original.endswith(
            "\n"
        ):
            replacement += "\n"

        lines[index] = replacement
        return "".join(
            lines
        )

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> int:

        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

