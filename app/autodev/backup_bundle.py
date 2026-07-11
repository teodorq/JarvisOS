import json
import shutil
from datetime import datetime
from pathlib import Path


class BackupBundleManager:

    def __init__(self):
        self.backup_root = Path("data/backups/autodev")
        self.backup_root.mkdir(parents=True, exist_ok=True)

        self.last_bundle_path = None

    def create_bundle(self, files: list[str], goal: str = "") -> dict:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        bundle_path = self.backup_root / timestamp
        files_path = bundle_path / "files"

        files_path.mkdir(parents=True, exist_ok=True)

        manifest = {
            "created_at": datetime.now().isoformat(),
            "goal": goal,
            "bundle_path": str(bundle_path),
            "files": [],
            "errors": []
        }

        unique_files = []

        for raw_path in files:
            if not raw_path:
                continue

            normalized = str(Path(raw_path))

            if normalized not in unique_files:
                unique_files.append(normalized)

        for raw_path in unique_files:
            source = Path(raw_path)

            if not source.exists():
                manifest["errors"].append(
                    f"Plik nie istnieje: {source}"
                )
                continue

            if not source.is_file():
                manifest["errors"].append(
                    f"To nie jest plik: {source}"
                )
                continue

            relative_name = self._safe_backup_name(source)
            backup_path = files_path / relative_name

            try:
                shutil.copy2(source, backup_path)

                manifest["files"].append({
                    "source": str(source),
                    "backup": str(backup_path)
                })

            except Exception as error:
                manifest["errors"].append(
                    f"Nie udało się zapisać {source}: {error}"
                )

        manifest_path = bundle_path / "manifest.json"

        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(
                manifest,
                file,
                ensure_ascii=False,
                indent=4
            )

        self.last_bundle_path = str(bundle_path)

        return manifest

    def restore_bundle(self, bundle_path: str | None = None) -> dict:
        selected_path = bundle_path or self.last_bundle_path

        result = {
            "success": False,
            "bundle_path": selected_path or "",
            "restored": [],
            "errors": []
        }

        if not selected_path:
            result["errors"].append(
                "Nie wskazano backupu do przywrócenia."
            )
            return result

        bundle = Path(selected_path)
        manifest_path = bundle / "manifest.json"

        if not manifest_path.exists():
            result["errors"].append(
                f"Brak manifestu: {manifest_path}"
            )
            return result

        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                manifest = json.load(file)

        except Exception as error:
            result["errors"].append(
                f"Nie udało się odczytać manifestu: {error}"
            )
            return result

        for item in manifest.get("files", []):
            source_path = Path(item.get("source", ""))
            backup_path = Path(item.get("backup", ""))

            if not backup_path.exists():
                result["errors"].append(
                    f"Brak pliku backupu: {backup_path}"
                )
                continue

            try:
                source_path.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                shutil.copy2(
                    backup_path,
                    source_path
                )

                result["restored"].append(
                    str(source_path)
                )

            except Exception as error:
                result["errors"].append(
                    f"Nie udało się przywrócić "
                    f"{source_path}: {error}"
                )

        result["success"] = (
            len(result["restored"]) > 0
            and not result["errors"]
        )

        return result

    def list_bundles(self) -> list[dict]:
        bundles = []

        for path in self.backup_root.iterdir():
            if not path.is_dir():
                continue

            manifest_path = path / "manifest.json"

            if not manifest_path.exists():
                continue

            try:
                with open(
                    manifest_path,
                    "r",
                    encoding="utf-8"
                ) as file:
                    manifest = json.load(file)

                bundles.append({
                    "path": str(path),
                    "created_at": manifest.get(
                        "created_at",
                        ""
                    ),
                    "goal": manifest.get(
                        "goal",
                        ""
                    ),
                    "files_count": len(
                        manifest.get("files", [])
                    ),
                    "errors_count": len(
                        manifest.get("errors", [])
                    )
                })

            except Exception:
                continue

        bundles.sort(
            key=lambda item: item.get(
                "created_at",
                ""
            ),
            reverse=True
        )

        return bundles

    def summary(self) -> str:
        bundles = self.list_bundles()

        if not bundles:
            return "Brak backupów AutoDev."

        lines = ["AUTODEV BACKUPS"]

        for item in bundles[:20]:
            lines.append(
                f"- {item['created_at']} | "
                f"pliki: {item['files_count']} | "
                f"błędy: {item['errors_count']} | "
                f"{item['goal']}"
            )
            lines.append(
                f"  {item['path']}"
            )

        return "\n".join(lines)

    def _safe_backup_name(self, source: Path) -> str:
        raw = str(source.resolve())

        safe = raw.replace(":", "")
        safe = safe.replace("\\", "__")
        safe = safe.replace("/", "__")

        return safe