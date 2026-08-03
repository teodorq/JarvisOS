from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
import unittest
from typing import Any


PROJECT_ROOT = Path(
    os.environ.get("JARVIS_PROJECT_ROOT", Path(__file__).resolve().parents[1])
).resolve()
os.chdir(PROJECT_ROOT)
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)


def _option_path(
    argv: list[str], option: str, *, required: bool = True
) -> Path | None:
    try:
        index = argv.index(option)
        value = argv[index + 1]
    except (ValueError, IndexError) as error:
        if required:
            raise ValueError(f"Expected {option} PATH.") from error
        return None
    return Path(value).resolve()


def _arguments(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _suite(args: list[str]) -> tuple[unittest.TestSuite, int]:
    verbosity = 2 if "-v" in args else 1
    args = [item for item in args if item != "-v"]
    if not args:
        raise ValueError("No test arguments.")
    loader = unittest.defaultTestLoader
    if args[0] == "discover":
        start = "tests"
        pattern = "test_*.py"
        index = 1
        while index < len(args):
            if args[index] == "-s" and index + 1 < len(args):
                start = args[index + 1]
                index += 2
            elif args[index] == "-p" and index + 1 < len(args):
                pattern = args[index + 1]
                index += 2
            else:
                index += 1
        return loader.discover(start, pattern=pattern), verbosity
    return loader.loadTestsFromNames(args), verbosity


def _run(args_path: Path) -> tuple[int, dict[str, Any]]:
    suite, verbosity = _suite(_arguments(args_path))
    count = suite.countTestCases()
    print(f"SAFE_TEST_COUNT={count}", flush=True)
    if count <= 0:
        return 3, {
            "status": "ERROR",
            "tests": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "reason": "zero_tests",
        }
    result = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=verbosity,
        buffer=False,
    ).run(suite)
    payload = {
        "status": "PASSED" if result.wasSuccessful() else "FAILED",
        "tests": int(result.testsRun),
        "discovered": int(count),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(getattr(result, "skipped", [])),
    }
    print(f"SAFE_TEST_STATUS={payload['status']}", flush=True)
    return (0 if result.wasSuccessful() else 1), payload


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    result_path = _option_path(raw, "--result-file", required=False)
    args_path = _option_path(raw, "--args-file")
    if args_path is None:
        raise ValueError("Missing test argument file.")
    code = 1
    payload: dict[str, Any] = {
        "status": "ERROR",
        "tests": 0,
        "failures": 0,
        "errors": 1,
        "skipped": 0,
    }
    try:
        code, payload = _run(args_path)
    except BaseException as error:
        traceback.print_exc()
        payload["reason"] = type(error).__name__
        payload["message"] = str(error)
        code = 1
    finally:
        if result_path is not None:
            _atomic_json(result_path, payload)
    return code


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(exit_code)
