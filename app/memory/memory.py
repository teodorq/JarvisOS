from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class Memory:

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        memory_file: str | Path | None = None,
    ) -> None:
        paths = ProjectPaths.from_value(
            project_root
        )
        self.memory_file = (
            Path(memory_file)
            if memory_file is not None
            else paths.main_memory_file
        ).expanduser().resolve(
            strict=False
        )
        self._store = JsonStore(
            self.memory_file,
            self._default_memory,
        )

        if not self._store.exists():
            self._save(
                self._default_memory()
            )
        else:
            self._migrate()

    def _default_memory(
        self,
    ) -> dict[str, Any]:
        return {
            "created_at": datetime.now().isoformat(),
            "version": "2.0",
            "notes": [],
            "tasks": [],
            "history": [],
            "knowledge": [],
            "experiences": [],
            "applications": {},
            "preferences": {},
        }

    def _load(
        self,
    ) -> dict[str, Any]:
        data = self._store.load()

        if not isinstance(
            data,
            dict,
        ):
            return self._default_memory()

        return data

    def _save(
        self,
        data: dict[str, Any],
    ) -> None:
        self._store.save(
            data
        )

    def _update(
        self,
        transform: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        def apply(value: object) -> dict[str, Any]:
            data = value if isinstance(value, dict) else self._default_memory()
            transform(data)
            return data

        return self._store.update(apply)

    def _migrate(
        self,
    ) -> None:
        data = self._load()
        default = self._default_memory()
        changed = False

        for key, value in default.items():
            if key not in data:
                data[key] = value
                changed = True

        if data.get("version") != "2.0":
            data["version"] = "2.0"
            changed = True

        if changed:
            self._save(
                data
            )

    def remember_note(
        self,
        text,
    ):
        note = {
            "text": text,
            "created_at": datetime.now().isoformat(),
        }
        self._update(
            lambda data: data["notes"].append(note)
        )
        return "Zapamiętałem notatkę."

    def add_task(
        self,
        text,
    ):
        task = {
            "text": text,
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }
        self._update(
            lambda data: data["tasks"].append(task)
        )
        return "Dodałem zadanie."

    def add_history(
        self,
        user_text,
        jarvis_text,
    ):
        item = {
            "user": user_text,
            "jarvis": jarvis_text,
            "created_at": datetime.now().isoformat(),
        }

        def append(data: dict[str, Any]) -> None:
            data["history"].append(item)
            if len(data["history"]) > 1000:
                data["history"] = data["history"][-1000:]

        self._update(append)

    def remember_knowledge(
        self,
        title,
        content,
    ):
        item = {
            "title": title,
            "content": content,
            "created_at": datetime.now().isoformat(),
        }
        self._update(
            lambda data: data["knowledge"].append(item)
        )

    def remember_experience(
        self,
        goal,
        success,
        summary,
    ):
        item = {
            "goal": goal,
            "success": success,
            "summary": summary,
            "created_at": datetime.now().isoformat(),
        }
        self._update(
            lambda data: data["experiences"].append(item)
        )

    def remember_application(
        self,
        app_name,
        info,
    ):
        self._update(
            lambda data: data["applications"].__setitem__(app_name, info)
        )

    def set_preference(
        self,
        key,
        value,
    ):
        self._update(
            lambda data: data["preferences"].__setitem__(key, value)
        )

    def get_preference(
        self,
        key,
        default=None,
    ):
        data = self._load()
        return data.get(
            "preferences",
            {},
        ).get(
            key,
            default,
        )

    def search_notes(
        self,
        text,
    ):
        data = self._load()
        return [
            note
            for note in data.get(
                "notes",
                [],
            )
            if text.lower()
            in note.get(
                "text",
                "",
            ).lower()
        ]

    def search_knowledge(
        self,
        text,
    ):
        data = self._load()
        results = []

        for item in data.get(
            "knowledge",
            [],
        ):
            title = item.get(
                "title",
                "",
            )
            content = item.get(
                "content",
                "",
            )

            if (
                text.lower() in title.lower()
                or text.lower() in content.lower()
            ):
                results.append(
                    item
                )

        return results

    def last_history(
        self,
        count=10,
    ):
        data = self._load()
        return data.get(
            "history",
            [],
        )[-count:]

    def get_summary(
        self,
    ):
        data = self._load()

        return (
            "Memory 2.0\n"
            f"Notatki: {len(data.get('notes', []))}\n"
            f"Zadania: {len(data.get('tasks', []))}\n"
            f"Historia: {len(data.get('history', []))}\n"
            f"Wiedza: {len(data.get('knowledge', []))}\n"
            f"Doświadczenia: {len(data.get('experiences', []))}\n"
            f"Aplikacje: {len(data.get('applications', {}))}\n"
            f"Preferencje: {len(data.get('preferences', {}))}"
        )
