import py_compile
from pathlib import Path


class SyntaxChecker:

    def check_file(self, path: str):
        file_path = Path(path)

        if not file_path.exists():
            return f"Plik nie istnieje: {path}"

        try:
            py_compile.compile(
                str(file_path),
                doraise=True
            )

            return f"SYNTAX OK: {file_path}"

        except Exception as error:
            return (
                f"SYNTAX ERROR: {file_path}\n"
                f"{error}"
            )