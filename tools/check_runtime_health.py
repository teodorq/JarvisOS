from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.performance_profile import load_performance_profile


def directory_size(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return total
    for root, _directories, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def measure_main_window_import(root: Path, timeout: float = 30.0) -> float:
    code = (
        "import time; started=time.perf_counter(); "
        "import app.gui.main_window; "
        "print(time.perf_counter()-started)"
    )
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=max(1.0, float(timeout)),
        check=True,
    )
    return float(result.stdout.strip().splitlines()[-1])


def measure_main_window_construction(root: Path, timeout: float = 30.0) -> float:
    code = (
        "import time; from PySide6.QtWidgets import QApplication; "
        "app=QApplication.instance() or QApplication([]); "
        "from app.gui.main_window import MainWindow; "
        "started=time.perf_counter(); window=MainWindow(); "
        "elapsed=time.perf_counter()-started; window.close(); print(elapsed)"
    )
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=root, env=environment,
        capture_output=True, text=True, timeout=max(1.0, float(timeout)),
        check=True,
    )
    return float(result.stdout.strip().splitlines()[-1])


def collect_runtime_health(project_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(project_root or PROJECT_ROOT).resolve()
    screenshots = root / "data" / "screenshots"
    screenshot_files = [path for path in screenshots.glob("*") if path.is_file()]
    startup_seconds = measure_main_window_import(root)
    construction_seconds = measure_main_window_construction(root)
    profile = load_performance_profile(root)
    return {
        "profile": profile.name,
        "main_window_import_seconds": round(startup_seconds, 3),
        "startup_target_seconds": 1.5,
        "startup_within_target": startup_seconds <= 1.5,
        "main_window_construct_seconds": round(construction_seconds, 3),
        "construction_target_seconds": 1.0,
        "construction_within_target": construction_seconds <= 1.0,
        "active_environment_bytes": directory_size(root / ".venv"),
        "runtime_bytes": directory_size(root / "runtime"),
        "autodev_bytes": directory_size(root / "data" / "autodev"),
        "screenshot_count": len(screenshot_files),
        "screenshot_bytes": sum(path.stat().st_size for path in screenshot_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS OS runtime health")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = collect_runtime_health()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            "JARVIS OS: "
            f"profil {report['profile']}, start {report['main_window_import_seconds']} s, "
            f"okno {report['main_window_construct_seconds']} s, "
            f"środowisko {report['active_environment_bytes'] / 1024**2:.1f} MiB, "
            f"zrzuty {report['screenshot_count']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
