import json
from datetime import datetime
from pathlib import Path


class Memory:
    def __init__(self):
        self.memory_file = Path("data/memory.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self._save({
                "created_at": datetime.now().isoformat(),
                "notes": [],
                "tasks": [],
                "history": []
            })

    def _load(self) -> dict:
        with open(self.memory_file, "r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, data: dict):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def remember_note(self, text: str) -> str:
        data = self._load()
        data["notes"].append({
            "text": text,
            "created_at": datetime.now().isoformat()
        })
        self._save(data)
        return "Zapamiętałem notatkę."

    def add_task(self, text: str) -> str:
        data = self._load()
        data["tasks"].append({
            "text": text,
            "status": "active",
            "created_at": datetime.now().isoformat()
        })
        self._save(data)
        return "Dodałem zadanie do pamięci."

    def add_history(self, user_text: str, jarvis_text: str):
        data = self._load()
        data["history"].append({
            "user": user_text,
            "jarvis": jarvis_text,
            "created_at": datetime.now().isoformat()
        })
        self._save(data)

    def get_summary(self) -> str:
        data = self._load()

        notes_count = len(data.get("notes", []))
        tasks_count = len(data.get("tasks", []))
        history_count = len(data.get("history", []))

        return (
            f"Pamięć aktywna. "
            f"Notatki: {notes_count}, "
            f"zadania: {tasks_count}, "
            f"historia: {history_count}."
        )