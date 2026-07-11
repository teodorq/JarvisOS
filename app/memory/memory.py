import json
from datetime import datetime
from pathlib import Path


class Memory:

    def __init__(self):
        self.memory_file = Path("data/memory.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self._save(self._default_memory())
        else:
            self._migrate()

    def _default_memory(self):
        return {
            "created_at": datetime.now().isoformat(),
            "version": "2.0",
            "notes": [],
            "tasks": [],
            "history": [],
            "knowledge": [],
            "experiences": [],
            "applications": {},
            "preferences": {}
        }

    def _load(self):
        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return self._default_memory()

            return data

        except Exception:
            return self._default_memory()

    def _save(self, data):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )

    def _migrate(self):
        data = self._load()
        default = self._default_memory()

        changed = False

        for key, value in default.items():
            if key not in data:
                data[key] = value
                changed = True

        if "version" not in data or data.get("version") != "2.0":
            data["version"] = "2.0"
            changed = True

        if changed:
            self._save(data)

    def remember_note(self, text):
        data = self._load()

        data["notes"].append({
            "text": text,
            "created_at": datetime.now().isoformat()
        })

        self._save(data)

        return "Zapamiętałem notatkę."

    def add_task(self, text):
        data = self._load()

        data["tasks"].append({
            "text": text,
            "status": "active",
            "created_at": datetime.now().isoformat()
        })

        self._save(data)

        return "Dodałem zadanie."

    def add_history(self, user_text, jarvis_text):
        data = self._load()

        data["history"].append({
            "user": user_text,
            "jarvis": jarvis_text,
            "created_at": datetime.now().isoformat()
        })

        if len(data["history"]) > 1000:
            data["history"] = data["history"][-1000:]

        self._save(data)

    def remember_knowledge(self, title, content):
        data = self._load()

        data["knowledge"].append({
            "title": title,
            "content": content,
            "created_at": datetime.now().isoformat()
        })

        self._save(data)

    def remember_experience(self, goal, success, summary):
        data = self._load()

        data["experiences"].append({
            "goal": goal,
            "success": success,
            "summary": summary,
            "created_at": datetime.now().isoformat()
        })

        self._save(data)

    def remember_application(self, app_name, info):
        data = self._load()

        data["applications"][app_name] = info

        self._save(data)

    def set_preference(self, key, value):
        data = self._load()

        data["preferences"][key] = value

        self._save(data)

    def get_preference(self, key, default=None):
        data = self._load()

        return data.get("preferences", {}).get(key, default)

    def search_notes(self, text):
        data = self._load()
        results = []

        for note in data.get("notes", []):
            if text.lower() in note.get("text", "").lower():
                results.append(note)

        return results

    def search_knowledge(self, text):
        data = self._load()
        results = []

        for item in data.get("knowledge", []):
            title = item.get("title", "")
            content = item.get("content", "")

            if text.lower() in title.lower() or text.lower() in content.lower():
                results.append(item)

        return results

    def last_history(self, count=10):
        data = self._load()

        return data.get("history", [])[-count:]

    def get_summary(self):
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