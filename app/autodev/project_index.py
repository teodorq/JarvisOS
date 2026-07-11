from dataclasses import dataclass, field

from app.autodev.project_file import (
    ProjectFile
)


@dataclass
class ProjectIndex:

    files: list[
        ProjectFile
    ] = field(
        default_factory=list
    )

    def add(
        self,
        file: ProjectFile
    ):
        self.files.append(file)

    def count(self):

        return len(self.files)

    def by_category(
        self,
        category: str
    ):

        return [
            f
            for f in self.files
            if f.category == category
        ]

    def summary(self):

        lines = [
            "PROJECT INDEX",
            f"Liczba plików: {len(self.files)}",
            ""
        ]

        for file in self.files:

            lines.append(
                file.path
            )

        return "\n".join(lines)