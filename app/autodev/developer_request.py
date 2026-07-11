from dataclasses import dataclass, field
from typing import Dict


@dataclass
class DeveloperRequest:

    goal: str
    target: str = ""
    mode: str = "file"

    path: str = ""
    proposed_content: str = ""

    function_name: str = ""
    new_function_code: str = ""

    replacements: Dict[str, str] = field(
        default_factory=dict
    )

    metadata: Dict[str, str] = field(
        default_factory=dict
    )

    def validate(self) -> tuple[bool, list[str]]:
        errors = []

        if not self.goal.strip():
            errors.append(
                "Brak celu zadania developerskiego."
            )

        allowed_modes = {
            "file",
            "function",
            "multi_file"
        }

        if self.mode not in allowed_modes:
            errors.append(
                f"Nieobsługiwany tryb: {self.mode}"
            )

        if self.mode == "file":
            if not self.path.strip():
                errors.append(
                    "Brak ścieżki pliku."
                )

            if not self.proposed_content:
                errors.append(
                    "Brak proponowanej zawartości pliku."
                )

        if self.mode == "function":
            if not self.path.strip():
                errors.append(
                    "Brak ścieżki pliku."
                )

            if not self.function_name.strip():
                errors.append(
                    "Brak nazwy funkcji."
                )

            if not self.new_function_code:
                errors.append(
                    "Brak nowego kodu funkcji."
                )

        if self.mode == "multi_file":
            if not self.replacements:
                errors.append(
                    "Brak zmian dla wielu plików."
                )

            for path, content in self.replacements.items():
                if not str(path).strip():
                    errors.append(
                        "Wykryto pustą ścieżkę pliku."
                    )

                if not content:
                    errors.append(
                        f"Brak nowej zawartości dla: {path}"
                    )

        return not errors, errors

    def summary(self) -> str:
        lines = [
            "DEVELOPER REQUEST",
            f"Cel: {self.goal}",
            f"Target: {self.target or 'brak'}",
            f"Tryb: {self.mode}"
        ]

        if self.mode in {
            "file",
            "function"
        }:
            lines.append(
                f"Plik: {self.path or 'brak'}"
            )

        if self.mode == "function":
            lines.append(
                f"Funkcja: "
                f"{self.function_name or 'brak'}"
            )

        if self.mode == "multi_file":
            lines.append(
                f"Liczba plików: "
                f"{len(self.replacements)}"
            )

            for path in self.replacements:
                lines.append(
                    f"- {path}"
                )

        if self.metadata:
            lines.append("")
            lines.append("Metadata:")

            for key, value in self.metadata.items():
                lines.append(
                    f"- {key}: {value}"
                )

        return "\n".join(lines)