"""Dedicated, inactive state store for a future Forex V3 shadow cohort."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from app.trading.forex_candidate_v3 import ForexStrengthCandidatePolicy
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_sample_contract import (
    build_forex_v3_shadow_sample_contract,
    verify_forex_v3_shadow_sample_contract,
)
from app.trading.models import TradingValidationError


class ForexV3ShadowLedger(ForexPaperLedger):
    """Keep V3 PAPER state separate; this class does not execute trades."""

    RELATIVE_PATH = Path(
        "data/trading/research/forex_v3_shadow_ledger.json"
    )
    MODE = "FOREX_V3_SHADOW_PAPER_ONLY"
    PORTFOLIO_ID = "FOREX_V3_SHADOW_PAPER"

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        initial_balance_pln: str = "100000",
        sample_contract: Mapping[str, Any] | None = None,
    ) -> None:
        selected = (
            sample_contract
            if sample_contract is not None
            else build_forex_v3_shadow_sample_contract()
        )
        if not verify_forex_v3_shadow_sample_contract(selected):
            raise TradingValidationError(
                "forex_v3_shadow: invalid_sample_contract"
            )
        self.sample_contract = deepcopy(dict(selected))
        super().__init__(
            project_root,
            initial_balance_pln=initial_balance_pln,
        )

    def _default(self) -> dict[str, Any]:
        state = super()._default()
        candidate = ForexStrengthCandidatePolicy()
        state.update({
            "portfolio_id": self.PORTFOLIO_ID,
            "candidate_id": candidate.candidate_id,
            "candidate_policy_fingerprint_sha256": (
                candidate.fingerprint_sha256
            ),
            "sample_contract_id": self.sample_contract["contract_id"],
            "sample_contract_fingerprint_sha256": self.sample_contract[
                "fingerprint_sha256"
            ],
        })
        return state

    def _normalized(self, value: object) -> dict[str, Any]:
        state = super()._normalized(value)
        expected = self._default()
        protected = (
            "portfolio_id",
            "candidate_id",
            "candidate_policy_fingerprint_sha256",
            "sample_contract_id",
            "sample_contract_fingerprint_sha256",
        )
        if any(state.get(key) != expected[key] for key in protected):
            state["mode"] = "INVALID"
        return state


__all__ = ["ForexV3ShadowLedger"]
