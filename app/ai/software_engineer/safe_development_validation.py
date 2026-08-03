from __future__ import annotations

import ast
import copy
import hashlib
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

from app.core.project_paths import resolve_project_root
from app.core.safe_process import SafeProcessRunner

from .safe_development_models import SafeDevelopmentPolicy, SafeDevelopmentSession


class SafeDevelopmentValidator:
    """Static and isolated runtime validation for a staged patch."""

    FORBIDDEN_INTRODUCTIONS = (
        "eval(", "exec(", "os.system(", "shell=True", "shell = True",
        "shutil.rmtree(", "winreg.", "requests.post(", "requests.put(",
        "requests.patch(", "requests.delete(",
    )

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: SafeDevelopmentPolicy | None = None,
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.policy = policy or SafeDevelopmentPolicy()
        self.python = str(Path(sys.executable).resolve(strict=False))
        self.process = SafeProcessRunner(
            project_root=self.project_root,
            allowed_executables=(self.python,),
            max_timeout_seconds=max(
                300,
                self.policy.focused_test_timeout_seconds,
                self.policy.live_test_timeout_seconds,
            ),
            max_output_chars=24_000,
        )

    def static_validate(
        self,
        session: SafeDevelopmentSession,
        *,
        original: str,
        proposed: str,
    ) -> dict[str, Any]:
        errors: list[str] = []
        checks: dict[str, Any] = {}
        checks["single_file"] = session.changed_files == [session.target]
        if not checks["single_file"]:
            errors.append("Poprawka nie jest ograniczona do jednego pliku.")
        checks["changed_lines"] = session.changed_lines
        if not 1 <= session.changed_lines <= self.policy.max_changed_lines:
            errors.append("Przekroczono limit zmienionych linii.")
        checks["hashes_match"] = (
            self._hash(original) == session.source_hash
            and self._hash(proposed) == session.proposed_hash
        )
        if not checks["hashes_match"]:
            errors.append("Hash artefaktów nie zgadza się z sesją.")
        try:
            old_tree = ast.parse(original, filename=session.target)
            new_tree = ast.parse(proposed, filename=session.target)
            checks["syntax_ok"] = True
        except SyntaxError as error:
            old_tree = None
            new_tree = None
            checks["syntax_ok"] = False
            errors.append(f"Błąd składni: linia {error.lineno or 0}, {error.msg}.")
        if old_tree is not None and new_tree is not None:
            checks["public_api_unchanged"] = (
                self._public_api(old_tree) == self._public_api(new_tree)
            )
            if not checks["public_api_unchanged"]:
                errors.append("Transformacja zmieniła publiczne klasy lub funkcje.")
            checks["transform_exact"] = self._transform_exact(
                session.transform,
                old_tree,
                new_tree,
                metadata=session.metadata,
            )
            if not checks["transform_exact"]:
                errors.append("Zmiana wykracza poza dozwoloną transformację.")
            checks["goal_aligned"] = self._goal_aligned(
                session.transform,
                old_tree,
                new_tree,
                metadata=session.metadata,
            )
            if not checks["goal_aligned"]:
                errors.append("Zmiana nie realizuje celu wybranego zadania.")
        introduced = [
            token for token in self.FORBIDDEN_INTRODUCTIONS
            if token in proposed and token not in original
        ]
        checks["forbidden_introductions"] = introduced
        if introduced:
            errors.append("Wprowadzono niedozwolone operacje: " + ", ".join(introduced))
        if "\x00" in proposed:
            errors.append("Proponowany kod zawiera znak NUL.")
        return {
            "success": not errors,
            "status": "STATIC_VALID" if not errors else "STATIC_REJECTED",
            "checks": checks,
            "errors": errors,
            "warnings": [],
        }

    def validate_workspace(
        self,
        session: SafeDevelopmentSession,
        *,
        deadline_monotonic: float | None = None,
    ) -> dict[str, Any]:
        workspace = Path(session.workspace_path)
        target = workspace / Path(session.target)
        if not target.is_file():
            return self._failed("WORKSPACE_TARGET_MISSING", "Brakuje targetu w workspace.")
        try:
            compile_timeout = self._bounded_timeout(60, deadline_monotonic)
        except TimeoutError as error:
            return self._failed("RUNTIME_BUDGET_REACHED", str(error))
        compile_result = self._run(
            workspace,
            [self.python, "-m", "py_compile", str(target)],
            timeout=compile_timeout,
        )
        if not compile_result["success"]:
            if self._deadline_exhausted(deadline_monotonic):
                return self._failed(
                    "RUNTIME_BUDGET_REACHED",
                    "Wyczerpano budżet czasu podczas kompilacji workspace.",
                    compile=compile_result,
                )
            return self._failed(
                "WORKSPACE_COMPILE_FAILED",
                "Kompilacja nie przeszła.",
                compile=compile_result,
            )
        module = self._module_name(session.target)
        try:
            import_timeout = self._bounded_timeout(60, deadline_monotonic)
        except TimeoutError as error:
            return self._failed(
                "RUNTIME_BUDGET_REACHED",
                str(error),
                compile=compile_result,
            )
        import_result = self._run(
            workspace,
            [
                self.python,
                "-u",
                str(workspace / "tools" / "safe_development_import_runner.py"),
                module,
            ],
            timeout=import_timeout,
        )
        if not import_result["success"]:
            if self._deadline_exhausted(deadline_monotonic):
                return self._failed(
                    "RUNTIME_BUDGET_REACHED",
                    "Wyczerpano budżet czasu podczas importu workspace.",
                    compile=compile_result,
                    import_result=import_result,
                )
            return self._failed(
                "WORKSPACE_IMPORT_FAILED",
                "Import zmienionego modułu nie przeszedł.",
                compile=compile_result,
                import_result=import_result,
            )
        modules = self.discover_focused_tests(workspace, session.target)
        try:
            test_timeout = self._bounded_timeout(
                self.policy.focused_test_timeout_seconds,
                deadline_monotonic,
            )
        except TimeoutError as error:
            return self._failed(
                "RUNTIME_BUDGET_REACHED",
                str(error),
                compile=compile_result,
                import_result=import_result,
            )
        tests = self._run_tests(
            workspace,
            modules,
            timeout=test_timeout,
        )
        if not tests["success"] and self._deadline_exhausted(deadline_monotonic):
            return self._failed(
                "RUNTIME_BUDGET_REACHED",
                "Wyczerpano budżet czasu podczas testów workspace.",
                compile=compile_result,
                import_result=import_result,
                tests=tests,
                focused_tests=modules,
            )
        success = bool(tests["success"])
        return {
            "success": success,
            "status": "WORKSPACE_VALIDATED" if success else "WORKSPACE_TESTS_FAILED",
            "compile": compile_result,
            "import": import_result,
            "tests": tests,
            "focused_tests": modules,
            "errors": [] if success else ["Testy na izolowanej kopii nie przeszły."],
        }

    def validate_live_target(self, session: SafeDevelopmentSession) -> dict[str, Any]:
        target = self.project_root / Path(session.target)
        compile_result = self._run(
            self.project_root,
            [self.python, "-m", "py_compile", str(target)],
            timeout=60,
        )
        tests = self._run_tests(
            self.project_root,
            list(session.focused_tests),
            timeout=self.policy.live_test_timeout_seconds,
        )
        success = compile_result["success"] and tests["success"]
        return {
            "success": success,
            "status": "LIVE_VALIDATED" if success else "LIVE_VALIDATION_FAILED",
            "compile": compile_result,
            "tests": tests,
            "focused_tests": list(session.focused_tests),
            "errors": [] if success else ["Walidacja po wdrożeniu nie przeszła."],
        }

    def discover_focused_tests(self, project_root: Path, target: str) -> list[str]:
        tests = project_root / "tests"
        if not tests.is_dir():
            return []
        module = self._module_name(target)
        stem = Path(target).stem
        direct: list[str] = []
        related: list[str] = []
        parent_marker = Path(target).parent.name
        for path in sorted(tests.glob("test_*.py")):
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            if module in source or stem in source:
                direct.append(f"tests.{path.stem}")
            elif parent_marker and parent_marker in path.stem:
                related.append(f"tests.{path.stem}")
        return (direct + related)[: self.policy.focused_test_limit]

    def _run_tests(
        self,
        project_root: Path,
        modules: list[str],
        *,
        timeout: float,
    ) -> dict[str, Any]:
        if not modules:
            return {
                "success": True,
                "status": "NO_DIRECT_TESTS",
                "count": 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            }
        state = project_root / ".safe_development"
        state.mkdir(parents=True, exist_ok=True)
        args_file = state / "focused_tests.txt"
        args_file.write_text("\n".join(modules) + "\n", encoding="utf-8")
        result = self._run(
            project_root,
            [
                self.python,
                "-u",
                str(project_root / "tools" / "safe_development_unittest_runner.py"),
                "--args-file",
                str(args_file),
            ],
            timeout=timeout,
        )
        output = result.get("stdout", "") + "\n" + result.get("stderr", "")
        match = re.search(r"SAFE_TEST_COUNT=(\d+)", output)
        result["count"] = int(match.group(1)) if match else 0
        if result["success"] and result["count"] <= 0:
            result["success"] = False
            result["status"] = "ZERO_TESTS"
        return result

    @staticmethod
    def _bounded_timeout(
        requested: float,
        deadline_monotonic: float | None,
    ) -> float:
        if deadline_monotonic is None:
            return float(requested)
        remaining = float(deadline_monotonic) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Wyczerpano budżet czasu kampanii AutoDev.")
        return max(0.05, min(float(requested), remaining))

    @staticmethod
    def _deadline_exhausted(deadline_monotonic: float | None) -> bool:
        return bool(
            deadline_monotonic is not None
            and time.monotonic() >= float(deadline_monotonic)
        )

    def _run(self, cwd: Path, command: list[str], *, timeout: float) -> dict[str, Any]:
        env = dict(os.environ)
        env.update({
            "JARVIS_PROJECT_ROOT": str(cwd),
            "PYTHONPATH": str(cwd),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        result = self.process.run(command, cwd=cwd, timeout=timeout, env=env)
        value = result.as_dict()
        value["success"] = result.success
        value["status"] = "PASSED" if result.success else (
            "TIMEOUT" if result.timed_out else "FAILED"
        )
        return value

    @staticmethod
    def _public_api(tree: ast.Module) -> tuple:
        result: list[tuple[str, str, int]] = []
        for node in tree.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            ):
                result.append(("function", node.name, len(node.args.args)))
            elif isinstance(node, ast.ClassDef):
                result.append(("class", node.name, len(node.bases)))
        return tuple(result)

    @staticmethod
    def _transform_exact(
        transform: str,
        old_tree: ast.Module,
        new_tree: ast.Module,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        if transform == "ENSURE_FINAL_NEWLINE":
            return ast.dump(old_tree) == ast.dump(new_tree)
        if transform == "ADD_FUNCTION_DOCSTRING":
            return SafeDevelopmentValidator._function_docstring_exact(
                old_tree,
                new_tree,
                str(dict(metadata or {}).get("function", "")),
            )
        if transform == "EXTRACT_FUNCTION_TAIL":
            return SafeDevelopmentValidator._function_tail_exact(
                old_tree,
                new_tree,
                dict(metadata or {}),
            )
        if transform != "ADD_MODULE_DOCSTRING":
            return False
        if ast.get_docstring(old_tree, clean=False) is not None:
            return False
        if ast.get_docstring(new_tree, clean=False) is None:
            return False
        new_body = list(new_tree.body)
        if (
            new_body
            and isinstance(new_body[0], ast.Expr)
            and isinstance(getattr(new_body[0], "value", None), ast.Constant)
            and isinstance(new_body[0].value.value, str)
        ):
            new_body = new_body[1:]
        return ast.dump(ast.Module(body=list(old_tree.body), type_ignores=[])) == ast.dump(
            ast.Module(body=new_body, type_ignores=[])
        )

    @staticmethod
    def _goal_aligned(
        transform: str,
        old_tree: ast.Module,
        new_tree: ast.Module,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        details = dict(metadata or {})
        issue_type = str(details.get("issue_type", "")).upper()
        if issue_type != "LONG_FUNCTION":
            return True
        if transform != "EXTRACT_FUNCTION_TAIL":
            return False
        name = str(details.get("function", ""))
        old_function = SafeDevelopmentValidator._named_function(old_tree, name)
        new_function = SafeDevelopmentValidator._named_function(new_tree, name)
        if old_function is None or new_function is None:
            return False
        old_length = (
            int(getattr(old_function, "end_lineno", old_function.lineno))
            - old_function.lineno
            + 1
        )
        new_length = (
            int(getattr(new_function, "end_lineno", new_function.lineno))
            - new_function.lineno
            + 1
        )
        return new_length < old_length

    @staticmethod
    def _named_function(
        tree: ast.Module,
        name: str,
    ) -> ast.FunctionDef | None:
        matches = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        matches.sort(key=lambda node: node.lineno)
        return matches[0] if matches else None

    @staticmethod
    def _function_tail_exact(
        old_tree: ast.Module,
        new_tree: ast.Module,
        metadata: dict[str, Any],
    ) -> bool:
        function_name = str(metadata.get("function", ""))
        helper_name = str(metadata.get("helper_name", ""))
        parameters = [
            str(item) for item in metadata.get("helper_parameters", [])
        ]
        if not function_name or not helper_name.startswith("_finish_"):
            return False
        rebuilt = copy.deepcopy(new_tree)
        helper: ast.FunctionDef | None = None
        target: ast.FunctionDef | None = None
        containers: list[list[ast.stmt]] = [rebuilt.body]
        containers.extend(
            node.body for node in ast.walk(rebuilt)
            if isinstance(node, ast.ClassDef)
        )
        for body in containers:
            local_target = next(
                (
                    node for node in body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == function_name
                ),
                None,
            )
            local_helper = next(
                (
                    node for node in body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == helper_name
                ),
                None,
            )
            if local_target is not None and local_helper is not None:
                target = local_target
                helper = local_helper
                body.remove(local_helper)
                break
        if target is None or helper is None:
            return False
        argument_names = [argument.arg for argument in helper.args.args]
        expected_arguments = list(parameters)
        if str(metadata.get("function_scope", "")) == "method":
            expected_arguments.insert(0, "self")
        if argument_names != expected_arguments:
            return False

        class InlineTail(ast.NodeTransformer):
            def __init__(self) -> None:
                self.replaced = 0

            def visit_Return(self, node: ast.Return):  # noqa: N802
                value = node.value
                if not isinstance(value, ast.Call):
                    return self.generic_visit(node)
                function = value.func
                called_name = ""
                if isinstance(function, ast.Name):
                    called_name = function.id
                elif isinstance(function, ast.Attribute):
                    called_name = function.attr
                arguments = [
                    argument.id for argument in value.args
                    if isinstance(argument, ast.Name)
                ]
                if called_name == helper_name and arguments == parameters:
                    self.replaced += 1
                    return [
                        copy.deepcopy(statement)
                        for statement in helper.body
                    ]
                return self.generic_visit(node)

        inliner = InlineTail()
        inliner.visit(target)
        if inliner.replaced != 1:
            return False
        ast.fix_missing_locations(rebuilt)
        return ast.dump(old_tree) == ast.dump(rebuilt)

    @staticmethod
    def _function_docstring_exact(
        old_tree: ast.Module,
        new_tree: ast.Module,
        function_name: str,
    ) -> bool:
        if not function_name:
            return False
        old_matches = [
            node for node in ast.walk(old_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ]
        new_matches = [
            node for node in ast.walk(new_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ]
        if len(old_matches) != len(new_matches) or not old_matches:
            return False
        pairs = sorted(zip(old_matches, new_matches), key=lambda pair: pair[0].lineno)
        changed = 0
        for old_node, new_node in pairs:
            old_dump = ast.dump(old_node)
            new_copy = ast.FunctionDef(
                name=new_node.name,
                args=new_node.args,
                body=list(new_node.body),
                decorator_list=new_node.decorator_list,
                returns=new_node.returns,
                type_comment=new_node.type_comment,
                type_params=getattr(new_node, "type_params", []),
            ) if isinstance(new_node, ast.FunctionDef) else ast.AsyncFunctionDef(
                name=new_node.name,
                args=new_node.args,
                body=list(new_node.body),
                decorator_list=new_node.decorator_list,
                returns=new_node.returns,
                type_comment=new_node.type_comment,
                type_params=getattr(new_node, "type_params", []),
            )
            if (
                new_copy.body
                and isinstance(new_copy.body[0], ast.Expr)
                and isinstance(getattr(new_copy.body[0], "value", None), ast.Constant)
                and isinstance(new_copy.body[0].value.value, str)
                and ast.get_docstring(old_node, clean=False) is None
            ):
                new_copy.body = new_copy.body[1:]
                changed += 1
            if old_dump != ast.dump(new_copy):
                return False
        if changed != 1:
            return False
        old_copy = ast.parse(ast.unparse(old_tree))
        new_copy_tree = ast.parse(ast.unparse(new_tree))
        for node in ast.walk(new_copy_tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
                and ast.get_docstring(node, clean=False) is not None
            ):
                node.body = node.body[1:]
                break
        return ast.dump(old_copy) == ast.dump(new_copy_tree)

    @staticmethod
    def _module_name(target: str) -> str:
        return ".".join(Path(target).with_suffix("").parts)

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _failed(status: str, message: str, **extra: Any) -> dict[str, Any]:
        return {"success": False, "status": status, "errors": [message], **extra}
