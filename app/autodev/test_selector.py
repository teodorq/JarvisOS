from pathlib import Path
from app.autodev.test_plan import TestPlan

class TestSelector:
    def build_plan(self, changed_files: list[str]) -> TestPlan:
        files = [str(Path(path)) for path in changed_files if str(path).strip()]
        commands = []

        for path in files:
            if Path(path).suffix.lower() == ".py":
                commands.append(["python", "-m", "py_compile", path])

        commands.append([
            "python", "-m", "unittest", "discover",
            "-s", "tests", "-p", "test_*.py"
        ])

        return TestPlan(
            changed_files=files,
            commands=commands,
        )
