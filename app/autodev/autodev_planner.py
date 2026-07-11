from __future__ import annotations

from typing import List, Dict


class AutoDevPlanner:

    def __init__(self):
        self.default_tasks = [
            {
                "title": "Improve Brain",
                "description": "Search for Brain improvements."
            },
            {
                "title": "Improve Memory",
                "description": "Search for Memory improvements."
            },
            {
                "title": "Improve Vision",
                "description": "Search for Vision improvements."
            },
            {
                "title": "Improve AutoDev",
                "description": "Search for AutoDev improvements."
            },
            {
                "title": "Improve UI",
                "description": "Search for UI improvements."
            }
        ]

    def generate_tasks(self) -> List[Dict]:
        return list(self.default_tasks)

    def add_task(
        self,
        title: str,
        description: str
    ):

        self.default_tasks.append(
            {
                "title": title,
                "description": description
            }
        )