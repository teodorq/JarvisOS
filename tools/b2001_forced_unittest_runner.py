from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)


def _read_arguments(argv: list[str]) -> list[str]:
    if len(argv) == 2 and argv[0] == "--args-file":
        path = Path(argv[1])
        if not path.is_file():
            raise FileNotFoundError(f"Missing test argument file: {path}")
        return [
            line.strip()
            for line in path.read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if line.strip()
        ]
    return list(argv)


def _discover_arguments(
    args: list[str],
) -> tuple[str, str, str | None]:
    start_dir = "tests"
    pattern = "test*.py"
    top_level_dir: str | None = None
    index = 1

    while index < len(args):
        item = args[index]
        if item == "-s" and index + 1 < len(args):
            start_dir = args[index + 1]
            index += 2
            continue
        if item == "-p" and index + 1 < len(args):
            pattern = args[index + 1]
            index += 2
            continue
        if item == "-t" and index + 1 < len(args):
            top_level_dir = args[index + 1]
            index += 2
            continue
        index += 1

    return start_dir, pattern, top_level_dir


def main() -> int:
    args = _read_arguments(list(sys.argv[1:]))

    if args[:2] == ["-m", "unittest"]:
        args = args[2:]

    verbosity = 1
    while "-v" in args:
        args.remove("-v")
        verbosity = 2

    if not args:
        print(
            "RUNNER_ERROR=no_test_arguments",
            file=sys.stderr,
        )
        return 2

    loader = unittest.defaultTestLoader
    if args[0] == "discover":
        start_dir, pattern, top_level_dir = (
            _discover_arguments(args)
        )
        suite = loader.discover(
            start_dir=start_dir,
            pattern=pattern,
            top_level_dir=top_level_dir,
        )
    else:
        suite = loader.loadTestsFromNames(args)

    count = suite.countTestCases()
    print(f"RUNNER_TEST_COUNT={count}", flush=True)

    if count <= 0:
        print(
            "RUNNER_ERROR=zero_tests_discovered",
            file=sys.stderr,
            flush=True,
        )
        return 3

    result = unittest.TextTestRunner(
        stream=sys.stdout,
        verbosity=verbosity,
        failfast=False,
        buffer=False,
    ).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except BaseException:
        traceback.print_exc()
        exit_code = 1
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            # Imported JARVIS modules may leave runtime threads alive.
            # The process is dedicated only to this isolated test run.
            os._exit(exit_code)
