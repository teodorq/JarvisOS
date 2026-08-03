from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from pathlib import Path


class ProjectScanner:

    def __init__(self, root_path=default_project_root()):
        self.root_path = Path(root_path)

    def list_python_files(self):
        files = []

        for path in self.root_path.rglob("*.py"):
            if "__pycache__" in str(path):
                continue

            files.append(str(path))

        return files

    def find_file(self, filename: str):
        filename = filename.lower().strip()

        for path in self.root_path.rglob("*"):
            if path.name.lower() == filename:
                return str(path)

        return None

    def find_files_containing(self, text: str):
        results = []
        text = text.lower()

        for path in self.root_path.rglob("*.py"):
            if "__pycache__" in str(path):
                continue

            try:
                content = path.read_text(encoding="utf-8").lower()

                if text in content:
                    results.append(str(path))

            except Exception:
                raise RuntimeError("AutoDev: przechwycony wyjątek")

        return results

    def summary(self):
        files = self.list_python_files()

        lines = [
            "PROJECT SCANNER",
            f"Root: {self.root_path}",
            f"Python files: {len(files)}",
            "",
            "Najważniejsze pliki:"
        ]

        for file in files[:30]:
            lines.append(f"- {file}")

        return "\n".join(lines)