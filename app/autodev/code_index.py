from app.autodev.project_index import (
    ProjectIndex
)


class CodeIndex:

    def __init__(
        self,
        index: ProjectIndex
    ):

        self.index = index

    def all(self):

        return self.index.files

    def count(self):

        return len(
            self.index.files
        )

    def summary(self):

        return (
            f"CodeIndex: "
            f"{self.count()} plików"
        )