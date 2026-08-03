from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any
import uuid

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9ąćęłńóśźżĄĆĘŁŃÓŚŹŻ_-]+", "-", str(value).strip())
    return text.strip("-").casefold()[:80] or "projekt"


class ProjectMemoryService:
    """B98 persistent projects, preferences and interrupted work state."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.root = root
        self.store = JsonStore(
            root / "data" / "assistant" / "project_memory.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "active_project_id": "",
            "projects": {},
            "preferences": {},
            "interrupted_tasks": [],
            "sessions": [],
            "updated_at": "",
        }

    def remember_project(
        self,
        name: str,
        *,
        path: str = "",
        summary: str = "",
        activate: bool = True,
    ) -> dict[str, Any]:
        clean_name = " ".join(str(name).split()).strip()
        if not clean_name:
            raise ValueError("Nazwa projektu nie może być pusta.")
        data = self._load()
        project_id = slug(clean_name)
        projects = dict(data.get("projects", {}) or {})
        existing = dict(projects.get(project_id, {}) or {})
        now = utc_now()
        projects[project_id] = {
            "project_id": project_id,
            "name": clean_name[:120],
            "path": str(path).strip()[:500],
            "summary": str(summary).strip()[:1000],
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "last_opened_at": now if activate else existing.get("last_opened_at", ""),
            "open_tasks": int(existing.get("open_tasks", 0)),
        }
        data["projects"] = projects
        if activate:
            data["active_project_id"] = project_id
        data["updated_at"] = now
        self.store.save(data)
        return projects[project_id]

    def activate_project(self, name_or_id: str) -> dict[str, Any]:
        data = self._load()
        projects = dict(data.get("projects", {}) or {})
        query = str(name_or_id).casefold().strip()
        match_id = next(
            (
                project_id
                for project_id, project in projects.items()
                if query in {project_id.casefold(), str(project.get("name", "")).casefold()}
            ),
            "",
        )
        if not match_id:
            raise KeyError(f"Nie znaleziono projektu: {name_or_id}")
        now = utc_now()
        project = dict(projects[match_id])
        project["last_opened_at"] = now
        project["updated_at"] = now
        projects[match_id] = project
        data["projects"] = projects
        data["active_project_id"] = match_id
        data["updated_at"] = now
        self.store.save(data)
        return project

    def set_preference(self, key: str, value: object) -> None:
        clean_key = slug(key)
        if not clean_key:
            raise ValueError("Klucz preferencji nie może być pusty.")
        data = self._load()
        preferences = dict(data.get("preferences", {}) or {})
        preferences[clean_key] = {
            "key": clean_key,
            "value": value,
            "updated_at": utc_now(),
        }
        data["preferences"] = preferences
        data["updated_at"] = utc_now()
        self.store.save(data)

    def get_preference(self, key: str, default: Any = None) -> Any:
        item = dict(self._load().get("preferences", {}).get(slug(key), {}) or {})
        return item.get("value", default)

    def interrupt_task(
        self,
        title: str,
        *,
        state: dict[str, Any] | None = None,
        project_id: str = "",
    ) -> dict[str, Any]:
        data = self._load()
        active = project_id or str(data.get("active_project_id", ""))
        task = {
            "task_id": uuid.uuid4().hex,
            "title": " ".join(str(title).split())[:160],
            "project_id": active,
            "state": dict(state or {}),
            "status": "INTERRUPTED",
            "created_at": utc_now(),
            "resumed_at": "",
        }
        tasks = list(data.get("interrupted_tasks", []) or [])
        tasks.append(task)
        data["interrupted_tasks"] = tasks[-200:]
        data["updated_at"] = utc_now()
        self.store.save(data)
        return task

    def resume_last_task(self) -> dict[str, Any] | None:
        data = self._load()
        tasks = list(data.get("interrupted_tasks", []) or [])
        for index in range(len(tasks) - 1, -1, -1):
            if str(tasks[index].get("status")) == "INTERRUPTED":
                task = dict(tasks[index])
                task["status"] = "RESUMED"
                task["resumed_at"] = utc_now()
                tasks[index] = task
                data["interrupted_tasks"] = tasks
                data["updated_at"] = utc_now()
                self.store.save(data)
                return task
        return None

    def add_session(self, summary: str, *, project_id: str = "") -> None:
        data = self._load()
        sessions = list(data.get("sessions", []) or [])
        sessions.append({
            "project_id": project_id or str(data.get("active_project_id", "")),
            "summary": str(summary).strip()[:1000],
            "created_at": utc_now(),
        })
        data["sessions"] = sessions[-200:]
        data["updated_at"] = utc_now()
        self.store.save(data)

    def status(self) -> dict[str, Any]:
        data = self._load()
        projects = dict(data.get("projects", {}) or {})
        active_id = str(data.get("active_project_id", ""))
        active = dict(projects.get(active_id, {}) or {})
        interrupted = [
            item
            for item in list(data.get("interrupted_tasks", []) or [])
            if str(item.get("status")) == "INTERRUPTED"
        ]
        return {
            "status": "PROJECT_MEMORY_READY",
            "project_count": len(projects),
            "active_project": active,
            "preference_count": len(dict(data.get("preferences", {}) or {})),
            "interrupted_count": len(interrupted),
            "last_interrupted": interrupted[-1] if interrupted else None,
            "session_count": len(list(data.get("sessions", []) or [])),
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
