from pathlib import Path


class FileEditor:

    def read_file(self, path: str):
        file_path = Path(path)

        if not file_path.exists():
            return f"Plik nie istnieje: {path}"

        return file_path.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str):
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return f"Zapisano plik: {file_path}"

    def append_to_file(self, path: str, content: str):
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "a", encoding="utf-8") as file:
            file.write(content)

        return f"Dopisano do pliku: {file_path}"

    def file_exists(self, path: str):
        return Path(path).exists()