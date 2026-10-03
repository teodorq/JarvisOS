from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


QUICK_TESTS = (
    "tests/test_dependency_manifests.py",
    "tests/test_autodev_batch_storage.py",
    "tests/test_autodev_concurrent_storage.py",
    "tests/test_client_brain.py",
    "tests/test_performance_profile.py",
    "tests/test_halo_idle_performance.py",
    "tests/test_runtime_startup_profile.py",
    "tests/test_storage_retention.py",
    "tests/test_autodev_storage_retention.py",
    "tests/test_audit_a2_2_runtime_storage.py",
    "tests/test_audit_a5_final_integrity.py",
)


def build_commands(tier: str) -> list[list[str]]:
    selected = str(tier).strip().casefold()
    tests = list(QUICK_TESTS) if selected == "quick" else ["tests"]
    return [
        [sys.executable, "-m", "pytest", "-q", *tests],
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "app",
            "cloud_service",
            "tools",
        ],
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS OS quality checks")
    parser.add_argument("--tier", choices=("quick", "full"), default="quick")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    for command in build_commands(args.tier):
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return int(result.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
