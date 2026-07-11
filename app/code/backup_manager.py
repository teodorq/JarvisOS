import shutil
from datetime import datetime
from pathlib import Path


class BackupManager:

    def __init__(self):
        self.backup_root = Path("data/backups/code")
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def backup_file(self, path: str):
        source = Path(path)

        if not source.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = str(source).replace(":", "").replace("\\", "_").replace("/", "_")

        backup_path = self.backup_root / f"{timestamp}_{safe_name}"

        shutil.copy2(source, backup_path)

        return str(backup_path)

    def restore_file(self, backup_path: str, target_path: str):
        backup = Path(backup_path)
        target = Path(target_path)

        if not backup.exists():
            return f"Backup nie istnieje: {backup_path}"

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)

        return f"Przywrócono plik: {target}"

    def list_backups(self):
        backups = list(self.backup_root.glob("*"))

        if not backups:
            return "Brak backupów."

        backups = sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)

        lines = ["BACKUPY KODU:"]

        for backup in backups[:20]:
            lines.append(f"- {backup}")

        return "\n".join(lines)