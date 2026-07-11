import difflib


class DiffBuilder:

    def build(
        self,
        old_content: str,
        new_content: str,
        path: str = "file.py"
    ) -> str:

        old_lines = old_content.splitlines(
            keepends=True
        )

        new_lines = new_content.splitlines(
            keepends=True
        )

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{path} (stara wersja)",
            tofile=f"{path} (nowa wersja)",
            lineterm=""
        )

        result = "\n".join(diff)

        if not result.strip():
            return "Brak różnic."

        return result

    def build_many(
        self,
        changes: list[dict]
    ) -> str:

        sections = []

        for change in changes:
            path = change.get(
                "path",
                "unknown.py"
            )

            old_content = change.get(
                "old_content",
                ""
            )

            new_content = change.get(
                "new_content",
                ""
            )

            sections.append(
                self.build(
                    old_content=old_content,
                    new_content=new_content,
                    path=path
                )
            )

        if not sections:
            return "Brak zmian do pokazania."

        return (
            "\n\n"
            + "\n\n".join(sections)
        )