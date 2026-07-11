from pathlib import Path
import shutil


class FileManager:

    def list_folder(self, path: str):
        folder = Path(path)

        if not folder.exists():
            return f"Folder nie istnieje: {path}"

        if not folder.is_dir():
            return f"To nie jest folder: {path}"

        lines = [f"Folder: {folder}"]

        for item in folder.iterdir():
            kind = "DIR" if item.is_dir() else "FILE"
            lines.append(f"- [{kind}] {item.name}")

        return "\n".join(lines)

    def create_folder(self, path: str):
        folder = Path(path)
        folder.mkdir(parents=True, exist_ok=True)
        return f"Utworzono folder: {folder}"

    def copy_file(self, source: str, target: str):
        source_path = Path(source)
        target_path = Path(target)

        if not source_path.exists():
            return f"Plik nie istnieje: {source}"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

        return f"Skopiowano plik do: {target_path}"

    def move_file(self, source: str, target: str):
        source_path = Path(source)
        target_path = Path(target)

        if not source_path.exists():
            return f"Plik nie istnieje: {source}"

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_path))

        return f"Przeniesiono plik do: {target_path}"

    def delete_file(self, path: str):
        file_path = Path(path)

        if not file_path.exists():
            return f"Plik nie istnieje: {path}"

        if file_path.is_dir():
            return "Nie usuwam folderów tą komendą."

        file_path.unlink()
        return f"Usunięto plik: {file_path}"