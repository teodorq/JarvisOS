"""B101-B105 intelligence, desktop, memory and autonomy services."""

__all__ = ["IntelligenceSuiteController"]


def __getattr__(name: str):
    if name == "IntelligenceSuiteController":
        from app.intelligence.controller import IntelligenceSuiteController
        return IntelligenceSuiteController
    raise AttributeError(name)
