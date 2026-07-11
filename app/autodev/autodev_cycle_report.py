from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class AutoDevCycleReport:
    cycle_id: str
    goal: str
    success: bool
    status: str
    writes_code: bool
    approved: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        return "\n".join(
            [
                "AUTODEV CYCLE REPORT",
                f"Cycle ID: {self.cycle_id}",
                f"Cel: {self.goal}",
                f"Status: {self.status}",
                (
                    "Sukces: TAK"
                    if self.success
                    else "Sukces: NIE"
                ),
                (
                    "Zapis kodu: TAK"
                    if self.writes_code
                    else "Zapis kodu: NIE"
                ),
                (
                    "Akceptacja: TAK"
                    if self.approved
                    else "Akceptacja: NIE"
                ),
            ]
        )
