import subprocess
from pathlib import Path
from typing import Any
from app.autodev.test_plan import TestPlan

class TestRunner:
    def __init__(self, project_root: str = "C:/JarvisAI") -> None:
        self.project_root = Path(project_root)

    def run(self, plan: TestPlan) -> dict[str, Any]:
        results = []

        for command in plan.commands:
            try:
                process = subprocess.run(
                    command,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=plan.timeout_seconds,
                )
                item = {
                    "command": command,
                    "returncode": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "success": process.returncode == 0,
                }
            except Exception as error:
                item = {
                    "command": command,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"{type(error).__name__}: {error}",
                    "success": False,
                }

            results.append(item)

            if not item["success"]:
                break

        success = all(item["success"] for item in results)

        return {
            "success": success,
            "status": "PASSED" if success else "FAILED",
            "results": results,
            "commands_run": len(results),
        }
