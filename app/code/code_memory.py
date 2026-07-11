import json
from datetime import datetime
from pathlib import Path


class CodeMemory:

    def __init__(self):
        self.memory_file = Path("data/memory/code_memory.json")
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self.save([])

    def load(self):
        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return []

    def save(self, data):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def remember_analysis(self, target: str, result: str):
        data = self.load()

        data.append({
            "type": "analysis",
            "target": target,
            "result": result,
            "created_at": datetime.now().isoformat()
        })

        if len(data) > 200:
            data = data[-200:]

        self.save(data)

    def remember_patch(self, target: str, summary: str):
        data = self.load()

        data.append({
            "type": "patch",
            "target": target,
            "summary": summary,
            "created_at": datetime.now().isoformat()
        })

        if len(data) > 200:
            data = data[-200:]

        self.save(data)

    def summary(self):
        data = self.load()

        lines = [
            "CODE MEMORY",
            f"Zapisów: {len(data)}"
        ]

        for item in data[-10:]:
            lines.append(
                f"- {item.get('type')} | "
                f"{item.get('target')} | "
                f"{item.get('created_at')}"
            )

        return "\n".join(lines)