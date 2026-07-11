from dataclasses import dataclass


@dataclass
class ReasoningStrategy:

    name: str

    description: str

    risk_limit: float = 0.5

    auto_execute: bool = False

    require_backup: bool = True

    require_validation: bool = True