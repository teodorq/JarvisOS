from dataclasses import dataclass
from pathlib import Path

from app.code.backup_manager import BackupManager


@dataclass
class CodePatch:
    path: str
    target_type: str
    target_name: str
    old_code: str
    new_code: str
    approved: bool = False
    backup_path: str = ""


class CodePatchManager:

    def __init__(self):
        self.current_patch = None
        self.last_patch = None
        self.backups = BackupManager()

    def create_patch(
        self,
        path: str,
        target_type: str,
        target_name: str,
        old_code: str,
        new_code: str
    ):
        self.current_patch = CodePatch(
            path=path,
            target_type=target_type,
            target_name=target_name,
            old_code=old_code,
            new_code=new_code
        )

        return self.current_patch

    def has_patch(self):
        return self.current_patch is not None

    def show_patch(self):
        if not self.current_patch:
            return "Brak aktywnej poprawki."

        patch = self.current_patch

        return (
            "CODE PATCH\n"
            f"Plik: {patch.path}\n"
            f"Typ: {patch.target_type}\n"
            f"Nazwa: {patch.target_name}\n\n"
            "STARY KOD:\n"
            f"{patch.old_code}\n\n"
            "NOWY KOD:\n"
            f"{patch.new_code}"
        )

    def approve(self):
        if not self.current_patch:
            return "Brak poprawki do zatwierdzenia."

        self.current_patch.approved = True
        return "Poprawka zatwierdzona."

    def clear(self):
        self.current_patch = None
        return "Wyczyszczono aktywną poprawkę."

    def apply_patch(self):
        if not self.current_patch:
            return "Brak poprawki do zapisania."

        patch = self.current_patch

        if not patch.approved:
            return "Poprawka nie jest zatwierdzona."

        file_path = Path(patch.path)

        if not file_path.exists():
            return f"Plik nie istnieje: {patch.path}"

        content = file_path.read_text(encoding="utf-8")

        if patch.old_code not in content:
            return "Nie znaleziono starego kodu w pliku."

        backup_path = self.backups.backup_file(str(file_path))

        if backup_path:
            patch.backup_path = backup_path

        content = content.replace(patch.old_code, patch.new_code, 1)

        file_path.write_text(content, encoding="utf-8")

        self.last_patch = patch
        self.current_patch = None

        return (
            f"Zapisano poprawkę w pliku: {file_path}\n"
            f"Backup: {backup_path}"
        )

    def undo_last_patch(self):
        if not self.last_patch:
            return "Brak ostatniej poprawki do cofnięcia."

        if not self.last_patch.backup_path:
            return "Ostatnia poprawka nie ma backupu."

        return self.backups.restore_file(
            self.last_patch.backup_path,
            self.last_patch.path
        )

    def list_backups(self):
        return self.backups.list_backups()