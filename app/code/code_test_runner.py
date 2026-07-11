import subprocess

from app.code.syntax_checker import SyntaxChecker


class CodeTestRunner:

    def __init__(self):
        self.syntax = SyntaxChecker()

    def check_file(self, path: str):
        return self.syntax.check_file(path)

    def run_main_quick(self):
        return (
            "GUI TEST SKIPPED\n"
            "main.py jest aplikacją GUI i działa ciągle, więc nie testuję go timeoutem."
        )

    def run_import_test(self):
        try:
            result = subprocess.run(
                [
                    "python",
                    "-c",
                    "from app.gui.main_window import MainWindow; print('IMPORT OK')"
                ],
                cwd="C:/JarvisAI",
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                return "IMPORT TEST OK\n" + result.stdout

            return (
                "IMPORT TEST FAILED\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

        except Exception as error:
            return f"IMPORT TEST ERROR: {error}"

    def run_main(self):
        import_result = self.run_import_test()

        return (
            "PROJECT TEST\n\n"
            f"{import_result}\n\n"
            f"{self.run_main_quick()}"
        )