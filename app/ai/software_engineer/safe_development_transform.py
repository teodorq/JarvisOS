from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from app.core.project_paths import resolve_project_root

from .safe_development_models import SafeDevelopmentPolicy


@dataclass(frozen=True, slots=True)
class SafeTransformCandidate:
    target: str
    transform: str
    title: str
    rationale: str
    risk_score: float
    confidence: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafeTransformPlanner:
    """Selects deterministic single-file changes with a stable public API."""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: SafeDevelopmentPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or SafeDevelopmentPolicy()

    def select(self, preview: dict[str, Any] | None) -> SafeTransformCandidate:
        preferred = self._preferred_target(preview)
        metadata = self._preview_metadata(preview)
        exact_required = bool(metadata.get("require_exact_target", False))
        candidates: list[tuple[int, SafeTransformCandidate]] = []
        for path in self._candidate_paths(preferred):
            if exact_required and path != self._safe_path(preferred):
                continue
            candidate = self._candidate_for(path, preferred, metadata)
            if candidate is not None:
                candidates.append((self._rank(path, preferred), candidate))
        if not candidates:
            raise ValueError(
                "Nie znalazłem deterministycznej poprawki o wystarczająco niskim ryzyku."
            )
        candidates.sort(key=lambda item: (item[0], item[1].target))
        return candidates[0][1]

    def apply(self, candidate: SafeTransformCandidate, source: str) -> str:
        if candidate.transform == "ADD_MODULE_DOCSTRING":
            return self._add_module_docstring(source, candidate.target)
        if candidate.transform == "ADD_FUNCTION_DOCSTRING":
            return self._add_function_docstring(
                source,
                candidate.target,
                str(candidate.metadata.get("function", "")),
            )
        if candidate.transform == "EXTRACT_FUNCTION_TAIL":
            return self._extract_function_tail(
                source,
                candidate.target,
                candidate.metadata,
            )
        if candidate.transform == "ENSURE_FINAL_NEWLINE":
            return source.rstrip("\n") + "\n"
        raise ValueError("Nieobsługiwany rodzaj bezpiecznej transformacji.")

    def _candidate_paths(self, preferred: str):
        yielded: set[Path] = set()
        preferred_path = self._safe_path(preferred)
        if preferred_path is not None:
            yielded.add(preferred_path)
            yield preferred_path
            for path in sorted(preferred_path.parent.glob("*.py")):
                if path not in yielded:
                    yielded.add(path)
                    yield path
        roots = (
            self.project_root / "app" / "ai" / "software_engineer",
            self.project_root / "app" / "autodev",
            self.project_root / "app" / "ai",
            self.project_root / "app" / "gui",
            self.project_root / "app",
        )
        for root in roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.py")):
                if path not in yielded:
                    yielded.add(path)
                    yield path

    def _candidate_for(
        self,
        path: Path,
        preferred: str,
        preview_metadata: dict[str, Any],
    ) -> SafeTransformCandidate | None:
        try:
            relative = path.relative_to(self.project_root).as_posix()
            stat = path.stat()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
        except (OSError, UnicodeError, SyntaxError, ValueError):
            return None
        if (
            stat.st_size > self.policy.max_source_bytes
            or not self._allowed(relative)
            or path.name == "__init__.py"
            or len(source.splitlines()) < 3
        ):
            return None
        function_name = str(preview_metadata.get("function", "")).strip()
        issue_type = str(preview_metadata.get("issue_type", "")).strip().upper()
        if relative == preferred and function_name and issue_type == "LONG_FUNCTION":
            function = self._named_function(tree, function_name)
            extraction = self._tail_extraction(tree, function)
            if extraction is not None:
                return SafeTransformCandidate(
                    target=relative,
                    transform="EXTRACT_FUNCTION_TAIL",
                    title="Wydziel ko\u0144cowy etap d\u0142ugiej funkcji",
                    rationale=(
                        "Zmiana rzeczywi\u015bcie skraca wskazan\u0105 funkcj\u0119: przenosi jej "
                        "ko\u0144cowy, sp\u00f3jny etap do prywatnej funkcji pomocniczej bez "
                        "zmiany kolejno\u015bci operacji ani publicznego API."
                    ),
                    risk_score=min(
                        18.0,
                        float(preview_metadata.get("risk_score", 18.0)),
                    ),
                    confidence=0.96,
                    metadata={
                        **dict(preview_metadata),
                        **extraction,
                        "function": function_name,
                        "same_as_preview_target": True,
                        "public_api_expected_unchanged": True,
                    },
                )
            return None
        if relative == preferred and function_name:
            function = self._function_without_docstring(tree, function_name)
            if function is not None:
                return SafeTransformCandidate(
                    target=relative,
                    transform="ADD_FUNCTION_DOCSTRING",
                    title="Dodaj kontrakt odpowiedzialności długiej funkcji",
                    rationale=(
                        "To najmniejszy bezpieczny krok dla zadania z backlogu: "
                        "opisuje odpowiedzialność funkcji przed jej późniejszym podziałem."
                    ),
                    risk_score=min(8.0, float(preview_metadata.get("risk_score", 8.0))),
                    confidence=0.99,
                    metadata={
                        **dict(preview_metadata),
                        "function": function_name,
                        "function_line": int(function.lineno),
                        "same_as_preview_target": True,
                        "public_api_expected_unchanged": True,
                    },
                )
        if ast.get_docstring(tree, clean=False) is None:
            same_target = relative == preferred
            rationale = (
                "To najmniejszy bezpieczny krok w module wskazanym przez wcześniejszą "
                "analizę: opisuje odpowiedzialność przed dalszym wydzielaniem kodu."
                if same_target
                else
                "Moduł nie ma opisu odpowiedzialności. Dodanie docstringu nie zmienia "
                "publicznego API ani zachowania wykonawczego."
            )
            return SafeTransformCandidate(
                target=relative,
                transform="ADD_MODULE_DOCSTRING",
                title="Dodaj opis odpowiedzialności modułu",
                rationale=rationale,
                risk_score=6.0 if same_target else 4.0,
                confidence=0.99,
                metadata={
                    "line_count": len(source.splitlines()),
                    "same_as_preview_target": same_target,
                    "public_api_expected_unchanged": True,
                },
            )
        if not source.endswith("\n"):
            return SafeTransformCandidate(
                target=relative,
                transform="ENSURE_FINAL_NEWLINE",
                title="Ujednolić zakończenie pliku",
                rationale=(
                    "Plik nie kończy się znakiem nowej linii. Zmiana jest "
                    "deterministyczna i nie zmienia API."
                ),
                risk_score=2.0,
                confidence=1.0,
                metadata={
                    "line_count": len(source.splitlines()),
                    "same_as_preview_target": relative == preferred,
                    "public_api_expected_unchanged": True,
                },
            )
        return None

    def _safe_path(self, relative: str) -> Path | None:
        value = str(relative or "").replace("\\", "/").strip("/")
        if not value or not self._allowed(value):
            return None
        candidate = (self.project_root / Path(value)).resolve(strict=False)
        try:
            candidate.relative_to(self.project_root)
        except ValueError:
            return None
        if not candidate.is_file() or candidate.is_symlink():
            return None
        return candidate

    def _allowed(self, relative: str) -> bool:
        normalized = "/" + str(relative).replace("\\", "/").strip("/") + "/"
        if not any(relative.startswith(prefix) for prefix in self.policy.allowed_prefixes):
            return False
        return not any(
            fragment.casefold() in normalized.casefold()
            for fragment in self.policy.protected_fragments
        )

    @staticmethod
    def _preferred_target(preview: dict[str, Any] | None) -> str:
        task = dict(dict(preview or {}).get("task", {}) or {})
        return str(task.get("target", "")).replace("\\", "/").strip("/")

    @staticmethod
    def _preview_metadata(preview: dict[str, Any] | None) -> dict[str, Any]:
        task = dict(dict(preview or {}).get("task", {}) or {})
        metadata = dict(task.get("metadata", {}) or {})
        if dict(preview or {}).get("backlog_task"):
            metadata.update(
                dict(dict(preview or {}).get("backlog_task", {}).get("metadata", {}) or {})
            )
        return metadata

    @staticmethod
    def _function_without_docstring(
        tree: ast.Module,
        name: str,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        matches = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
            and ast.get_docstring(node, clean=False) is None
        ]
        matches.sort(
            key=lambda node: (
                -(int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno)),
                int(node.lineno),
            )
        )
        return matches[0] if matches else None

    @staticmethod
    def _named_function(
        tree: ast.Module,
        name: str,
    ) -> ast.FunctionDef | None:
        matches = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        matches.sort(
            key=lambda node: (
                -(int(getattr(node, "end_lineno", node.lineno)) - node.lineno),
                node.lineno,
            )
        )
        return matches[0] if matches else None

    @classmethod
    def _tail_extraction(
        cls,
        tree: ast.Module,
        function: ast.FunctionDef | None,
    ) -> dict[str, Any] | None:
        if function is None or len(function.body) < 3:
            return None
        if function.decorator_list or not isinstance(function.body[-1], ast.Return):
            return None
        allowed = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Return)
        suffix: list[ast.stmt] = []
        for statement in reversed(function.body):
            if not isinstance(statement, allowed):
                break
            if any(
                isinstance(node, (ast.Await, ast.Yield, ast.YieldFrom))
                for node in ast.walk(statement)
            ):
                break
            suffix.append(statement)
            if len(suffix) >= 6:
                break
        suffix.reverse()
        if len(suffix) < 2 or not isinstance(suffix[-1], ast.Return):
            return None
        if any(isinstance(statement, ast.Return) for statement in suffix[:-1]):
            return None

        parent = next(
            (
                node for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and function in node.body
            ),
            None,
        )
        is_method = parent is not None
        argument_names = [argument.arg for argument in function.args.args]
        if is_method and (not argument_names or argument_names[0] != "self"):
            return None
        helper_name = f"_finish_{function.name}"
        scope_body = parent.body if parent is not None else tree.body
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == helper_name
            for node in scope_body
        ):
            return None

        parameters = cls._tail_inputs(
            suffix,
            exclude={"self"} if is_method else set(),
        )
        return {
            "helper_name": helper_name,
            "helper_parameters": parameters,
            "tail_start_line": int(suffix[0].lineno),
            "tail_end_line": int(
                getattr(suffix[-1], "end_lineno", suffix[-1].lineno)
            ),
            "function_line": int(function.lineno),
            "function_end_line": int(
                getattr(function, "end_lineno", function.lineno)
            ),
            "function_scope": "method" if is_method else "module",
        }

    @staticmethod
    def _tail_inputs(
        statements: list[ast.stmt],
        *,
        exclude: set[str],
    ) -> list[str]:
        assigned: set[str] = set()
        inputs: list[str] = []

        def remember(name: str) -> None:
            if name not in exclude and name not in assigned and name not in inputs:
                inputs.append(name)

        for statement in statements:
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    remember(node.id)
                elif isinstance(node, ast.AugAssign) and isinstance(
                    node.target, ast.Name
                ):
                    remember(node.target.id)
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    assigned.add(node.id)
        return inputs

    @classmethod
    def _extract_function_tail(
        cls,
        source: str,
        target: str,
        metadata: dict[str, Any],
    ) -> str:
        tree = ast.parse(source, filename=target)
        function_name = str(metadata.get("function", ""))
        function = cls._named_function(tree, function_name)
        extraction = cls._tail_extraction(tree, function)
        if function is None or extraction is None:
            raise ValueError("Nie znaleziono bezpiecznego ko\u0144cowego etapu funkcji.")
        for key in (
            "helper_name",
            "helper_parameters",
            "tail_start_line",
            "tail_end_line",
            "function_scope",
        ):
            if extraction.get(key) != metadata.get(key):
                raise ValueError(
                    "Kod \u017ar\u00f3d\u0142owy nie odpowiada zaplanowanej transformacji."
                )

        lines = source.splitlines(keepends=True)
        start = int(extraction["tail_start_line"]) - 1
        end = int(extraction["tail_end_line"])
        function_end = int(extraction["function_end_line"])
        block = lines[start:end]
        if not block:
            raise ValueError("Ko\u0144cowy etap funkcji jest pusty.")
        block_indent = re.match(r"\s*", block[0]).group(0)
        function_indent = re.match(
            r"\s*", lines[int(extraction["function_line"]) - 1]
        ).group(0)
        helper_body_indent = function_indent + "    "
        if len(block_indent) < len(helper_body_indent):
            raise ValueError("Nieprawid\u0142owe wci\u0119cie ko\u0144cowego etapu funkcji.")
        dedent = len(block_indent) - len(helper_body_indent)
        helper_body = [
            line[dedent:] if line.strip() else line
            for line in block
        ]
        parameters = list(extraction["helper_parameters"])
        call_target = (
            f"self.{extraction['helper_name']}"
            if extraction["function_scope"] == "method"
            else str(extraction["helper_name"])
        )
        call = (
            f"{block_indent}return {call_target}"
            f"({', '.join(parameters)})\n"
        )
        signature_parameters = list(parameters)
        if extraction["function_scope"] == "method":
            signature_parameters.insert(0, "self")
        helper = [
            "\n",
            f"{function_indent}def {extraction['helper_name']}"
            f"({', '.join(signature_parameters)}):\n",
            *helper_body,
        ]
        result = "".join(
            lines[:start]
            + [call]
            + lines[end:function_end]
            + helper
            + lines[function_end:]
        )
        ast.parse(result, filename=target)
        return result

    def _rank(self, path: Path, preferred: str) -> int:
        relative = path.relative_to(self.project_root).as_posix()
        if relative == preferred:
            return 0
        preferred_parent = str(Path(preferred).parent).replace("\\", "/")
        if preferred_parent and relative.startswith(preferred_parent.rstrip("/") + "/"):
            return 10
        if relative.startswith("app/ai/software_engineer/"):
            return 20
        if relative.startswith("app/autodev/"):
            return 30
        if relative.startswith("app/ai/"):
            return 40
        return 50

    @staticmethod
    def _add_function_docstring(
        source: str,
        target: str,
        function_name: str,
    ) -> str:
        tree = ast.parse(source, filename=target)
        function = SafeTransformPlanner._function_without_docstring(
            tree, function_name
        )
        if function is None or not function.body:
            raise ValueError("Nie znaleziono funkcji bez docstringu.")
        first = function.body[0]
        lines = source.splitlines(keepends=True)
        index = int(first.lineno) - 1
        indentation = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
        text = function_name.replace("_", " ").strip() or "runtime operation"
        lines.insert(
            index,
            f'{indentation}"""Coordinates {text} for the JARVIS OS runtime."""\n',
        )
        result = "".join(lines)
        ast.parse(result, filename=target)
        return result

    @staticmethod
    def _add_module_docstring(source: str, target: str) -> str:
        tree = ast.parse(source, filename=target)
        if ast.get_docstring(tree, clean=False) is not None:
            raise ValueError("Moduł posiada już docstring.")
        lines = source.splitlines(keepends=True)
        index = 1 if lines and lines[0].startswith("#!") else 0
        for offset in range(index, min(index + 2, len(lines))):
            text = lines[offset].casefold()
            if "coding" in text and text.lstrip().startswith("#"):
                index = offset + 1
        stem = Path(target).stem.replace("_", " ")
        lines.insert(index, f'"""Provides {stem} support for the JARVIS OS runtime."""\n\n')
        result = "".join(lines)
        ast.parse(result, filename=target)
        return result
