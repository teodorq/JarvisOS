from pathlib import Path


class FileClassifier:

    def classify(
        self,
        path: str
    ) -> str:

        path = str(
            Path(path)
        ).lower()

        if "vision" in path:
            return "vision"

        if "memory" in path:
            return "memory"

        if "voice" in path:
            return "voice"

        if "browser" in path:
            return "browser"

        if "desktop" in path:
            return "desktop"

        if "autodev" in path:
            return "autodev"

        if "gui" in path:
            return "gui"

        if "brain" in path:
            return "brain"

        return "other"