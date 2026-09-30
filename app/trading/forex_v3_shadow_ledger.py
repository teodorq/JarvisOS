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
            "initialization": {
                "status": "NOT_INITIALIZED",
                "initialized_at": "",
                "forward_evidence_content_sha256": "",
                "source_head_hash": "",
                "source_cutoff_sequence": 0,
                "execution_enabled": False,
            },
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
        initialization = dict(state.get("initialization", {}) or {})
        expected_initialization = expected["initialization"]
        for key, default in expected_initialization.items():
            initialization.setdefault(key, default)
        status = str(initialization.get("status", ""))
        if initialization.get("execution_enabled") is not False:
            state["mode"] = "INVALID"
        if status == "NOT_INITIALIZED":
            if any(
                initialization.get(key) not in ("", 0)
                for key in (
                    "initialized_at",
                    "forward_evidence_content_sha256",
                    "source_head_hash",
                    "source_cutoff_sequence",
                )
            ):
                state["mode"] = "INVALID"
        elif status == "INITIALIZED_SHADOW_INACTIVE":
            if (
                not str(initialization.get("initialized_at", ""))
                or len(
                    str(initialization.get(
                        "forward_evidence_content_sha256",
                        "",
                    ))
                ) != 64
                or len(str(initialization.get("source_head_hash", ""))) != 64
                or type(initialization.get("source_cutoff_sequence")) is not int
                or initialization.get("source_cutoff_sequence", 0) <= 0
            ):
                state["mode"] = "INVALID"
        else:
            state["mode"] = "INVALID"
        state["initialization"] = initialization
        return state


__all__ = ["ForexV3ShadowLedger"]
