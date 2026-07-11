from app.code.code_extractor import CodeExtractor
from app.code.code_memory import CodeMemory
from app.code.code_patch import CodePatchManager
from app.code.code_test_runner import CodeTestRunner
from app.code.file_editor import FileEditor
from app.code.project_scanner import ProjectScanner
from app.code.refactor_engine import RefactorEngine
from app.code.symbol_index import SymbolIndex


class CodeAgent:

    def __init__(self):
        self.scanner = ProjectScanner()
        self.editor = FileEditor()
        self.symbols = SymbolIndex()
        self.extractor = CodeExtractor()
        self.patches = CodePatchManager()
        self.refactor = RefactorEngine()
        self.memory = CodeMemory()
        self.tests = CodeTestRunner()

    def project_summary(self):
        return self.scanner.summary()

    def rebuild_index(self):
        self.symbols.rebuild()
        return self.symbols.summary()

    def find_file(self, filename: str):
        result = self.scanner.find_file(filename)

        if result:
            return f"Znaleziono plik:\n{result}"

        return f"Nie znaleziono pliku: {filename}"

    def find_code(self, text: str):
        results = self.scanner.find_files_containing(text)

        if not results:
            return f"Nie znaleziono kodu zawierającego: {text}"

        lines = [f"Znaleziono '{text}' w plikach:"]

        for path in results[:20]:
            lines.append(f"- {path}")

        return "\n".join(lines)

    def find_class(self, name: str):
        results = self.symbols.find_class(name)

        if not results:
            return f"Nie znaleziono klasy: {name}"

        lines = [f"Klasy pasujące do '{name}':"]

        for cls in results:
            lines.append(
                f"- {cls['name']}\n"
                f"  {cls['path']}\n"
                f"  linia {cls['line']}"
            )

        return "\n".join(lines)

    def find_function(self, name: str):
        results = self.symbols.find_function(name)

        if not results:
            return f"Nie znaleziono funkcji: {name}"

        lines = [f"Funkcje pasujące do '{name}':"]

        for func in results:
            lines.append(
                f"- {func['name']}\n"
                f"  {func['path']}\n"
                f"  linia {func['line']}"
            )

        return "\n".join(lines)

    def show_class(self, name: str):
        results = self.symbols.find_class(name)

        if not results:
            return f"Nie znaleziono klasy: {name}"

        cls = results[0]

        code = self.extractor.extract_class(
            cls["path"],
            cls["name"]
        )

        return (
            f"KLASA: {cls['name']}\n"
            f"PLIK: {cls['path']}\n"
            f"LINIA: {cls['line']}\n\n"
            f"{code}"
        )

    def show_function(self, name: str):
        results = self.symbols.find_function(name)

        if not results:
            return f"Nie znaleziono funkcji: {name}"

        func = results[0]

        code = self.extractor.extract_function(
            func["path"],
            func["name"]
        )

        return (
            f"FUNKCJA: {func['name']}\n"
            f"PLIK: {func['path']}\n"
            f"LINIA: {func['line']}\n\n"
            f"{code}"
        )

    def analyze_function(self, name: str):
        results = self.symbols.find_function(name)

        if not results:
            return f"Nie znaleziono funkcji: {name}"

        func = results[0]

        code = self.extractor.extract_function(
            func["path"],
            func["name"]
        )

        analysis = self.refactor.analyze_code(code)

        result = (
            f"ANALIZA FUNKCJI: {func['name']}\n"
            f"PLIK: {func['path']}\n"
            f"LINIA: {func['line']}\n\n"
            f"{analysis}"
        )

        self.memory.remember_analysis(name, result)

        return result

    def draft_mark_function(self, name: str):
        results = self.symbols.find_function(name)

        if not results:
            return f"Nie znaleziono funkcji: {name}"

        func = results[0]

        old_code = self.extractor.extract_function(
            func["path"],
            func["name"]
        )

        new_code = self.refactor.make_safe_header_comment(old_code)

        patch = self.patches.create_patch(
            path=func["path"],
            target_type="function",
            target_name=func["name"],
            old_code=old_code,
            new_code=new_code
        )

        self.memory.remember_patch(
            name,
            "Utworzono szkic oznaczenia funkcji komentarzem TODO."
        )

        return (
            "Utworzono bezpieczny szkic poprawki.\n"
            f"Plik: {patch.path}\n"
            f"Funkcja: {patch.target_name}\n\n"
            "Użyj komendy: pokaż poprawkę"
        )

    def draft_replace_function(self, name: str, new_code: str):
        results = self.symbols.find_function(name)

        if not results:
            return f"Nie znaleziono funkcji: {name}"

        func = results[0]

        old_code = self.extractor.extract_function(
            func["path"],
            func["name"]
        )

        patch = self.patches.create_patch(
            path=func["path"],
            target_type="function",
            target_name=func["name"],
            old_code=old_code,
            new_code=new_code
        )

        self.memory.remember_patch(
            name,
            "Utworzono szkic podmiany funkcji."
        )

        return (
            "Utworzono szkic poprawki.\n"
            f"Plik: {patch.path}\n"
            f"Funkcja: {patch.target_name}\n\n"
            "Użyj komendy: pokaż poprawkę"
        )

    def show_patch(self):
        return self.patches.show_patch()

    def approve_patch(self):
        return self.patches.approve()

    def apply_patch(self):
        result = self.patches.apply_patch()

        if result.startswith("Zapisano poprawkę"):
            test_result = self.tests.run_main()
            return result + "\n\n" + test_result

        return result

    def undo_patch(self):
        return self.patches.undo_last_patch()

    def list_backups(self):
        return self.patches.list_backups()

    def clear_patch(self):
        return self.patches.clear()

    def code_memory_summary(self):
        return self.memory.summary()

    def run_project_test(self):
        return self.tests.run_main()

    def read_file(self, path: str):
        return self.editor.read_file(path)

    def write_file(self, path: str, content: str):
        return self.editor.write_file(path, content)

    def append_to_file(self, path: str, content: str):
        return self.editor.append_to_file(path, content)