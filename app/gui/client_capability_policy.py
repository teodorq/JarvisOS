from __future__ import annotations

from app.assistant.natural_language import fold_text
from app.jarvis_experience.smart_task_loop import TaskOutcome
from app.natural_actions.business_day_understanding import classify_business_day


class ClientCapabilityPolicy:
    """Hard boundary between the sold client product and owner-only tools."""

    OWNER_ONLY_ASSISTANT_INTENTS = {
        "day_business_summary",
        "advertising_overview",
        "trading_overview",
        "paper_trading_status",
    }
    OWNER_ONLY_MARKERS = (
        "autodev",
        "samorozw",
        "rozwij siebie",
        "rozwijaj siebie",
        "rozwijaj sie",
        "sam sie rozwij",
        "ulepsz siebie",
        "programuj siebie",
        "programuj sie",
        "sam sie programuj",
        "samoprogram",
        "przygotowana poprawk",
        "poprawk projektu",
        "zmien kod",
        "kod projektu",
        "testy projektu",
        "debug",
        "terminal",
        "konsola operacyjna",
        "audyt",
        "licencj",
        "ustaw role",
        "zmien role",
        "profil organizacji",
        "checkpoint",
        "kopia zapasowa",
        "pakiet przywracania",
        "aktualizac systemu",
        "instalator",
        "wdrozenie",
        "wdroz",
        "release candidate",
        "rc1",
        "tryb wlasciciela",
        "panel wlasciciela",
        "ustawienia systemu",
        "konfiguracja business",
        "logi systemu",
        "status paper tradingu",
        "stan paper tradingu",
        "status tradingu",
        "gotowosc tradingu",
        "gotowosc do tradingu",
        "zabezpieczenia tradingu",
        "audyt tradingu",
        "status silnika tradingowego",
        "status forex",
        "gotowosc forex",
        "skaner forex",
    )
    OWNER_ONLY_THOUGHT_MARKERS = (
        "autodev",
        "software_engineer",
        "continuous_dev",
        "evolution",
        "architecture",
        "audit",
        "license",
        "backup",
        "recovery",
        "update_center",
        "release",
        "deployment",
        "organization",
        "business_admin",
        "owner",
    )
    OWNER_ONLY_HANDLER_PREFIXES = (
        "autodev",
        "autonomous_",
        "safe_autodev",
        "safe_development_",
        "software_engineer",
        "meta_executive",
        "executive_ai",
        "project_director",
        "self_improvement",
        "evolution",
        "continuous_dev",
        "reasoner",
        "research",
        "business_",
        "release_",
        "deployment",
    )
    OWNER_ONLY_ACTION_TYPES = {
        "run_command", "shell", "terminal", "write_file", "patch", "install", "deploy",
    }

    @classmethod
    def denial_message(cls, command: object) -> str:
        value = fold_text(command)
        classified = classify_business_day(value)
        if classified and classified[0] in cls.OWNER_ONLY_ASSISTANT_INTENTS:
            return cls._denial()
        if not any(marker in value for marker in cls.OWNER_ONLY_MARKERS):
            return ""
        return cls._denial()

    @classmethod
    def denial_for_thought(cls, thought: object) -> str:
        if not isinstance(thought, dict):
            return ""
        assistant_intent = fold_text(thought.get("assistant_intent", ""))
        if assistant_intent in cls.OWNER_ONLY_ASSISTANT_INTENTS:
            return cls._denial()
        handler = fold_text(thought.get("handler", ""))
        if any(
            handler.startswith(prefix)
            for prefix in cls.OWNER_ONLY_HANDLER_PREFIXES
        ):
            return cls._denial()
        values = [
            fold_text(thought.get(key, ""))
            for key in (
                "handler", "intent", "assistant_intent", "operation",
                "category", "module", "service", "capability",
            )
        ]
        for action in list(thought.get("actions", []) or []):
            if not isinstance(action, dict):
                continue
            action_type = fold_text(action.get("action_type", ""))
            if action_type in cls.OWNER_ONLY_ACTION_TYPES:
                return cls._denial()
            values.extend(
                fold_text(action.get(key, ""))
                for key in ("handler", "operation", "module", "service")
            )
        value = " ".join(values)
        if not any(marker in value for marker in cls.OWNER_ONLY_THOUGHT_MARKERS):
            return ""
        return cls._denial()

    @staticmethod
    def _denial() -> str:
        return (
            "Ta funkcja jest dostępna tylko w trybie właściciela JARVISA. "
            "W trybie klienta mogę pomóc w codziennej pracy, poczcie, "
            "kalendarzu, dokumentach, przypomnieniach i rachunkach."
        )


def enforce_client_outcome(outcome: TaskOutcome) -> TaskOutcome:
    """Reject owner-only plans even when their wording passed the first filter."""
    denial = ClientCapabilityPolicy.denial_for_thought(outcome.thought)
    if denial:
        return TaskOutcome("DENIED", denial)
    return outcome
