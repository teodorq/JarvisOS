from __future__ import annotations

import json

from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_sample_contract import (
    V3_SHADOW_CONTRACT_ID,
    build_forex_paper_sample_contract,
)
from app.trading.forex_v3_shadow_ledger import ForexV3ShadowLedger
from app.trading.models import TradingValidationError


def test_shadow_ledger_is_separate_and_snapshot_does_not_create_it(
    tmp_path,
) -> None:
    base = ForexPaperLedger(tmp_path)
    shadow = ForexV3ShadowLedger(tmp_path)

    state = shadow.snapshot()

    assert shadow.path != base.path
    assert shadow.path == (
        tmp_path / "data/trading/research/forex_v3_shadow_ledger.json"
    )
    assert state["mode"] == "FOREX_V3_SHADOW_PAPER_ONLY"
    assert state["portfolio_id"] == "FOREX_V3_SHADOW_PAPER"
    assert state["candidate_id"] == "FOREX_STRENGTH_V3_20260929"
    assert state["sample_contract_id"] == V3_SHADOW_CONTRACT_ID
    assert state["positions"] == {}
    assert state["fills"] == []
    assert not shadow.path.exists()
    assert not base.path.exists()


def test_shadow_ledger_rejects_base_contract(tmp_path) -> None:
    try:
        ForexV3ShadowLedger(
            tmp_path,
            sample_contract=build_forex_paper_sample_contract(),
        )
    except TradingValidationError as error:
        assert "invalid_sample_contract" in str(error)
    else:
        raise AssertionError("base contract unexpectedly accepted")


def test_shadow_ledger_persists_identity_and_detects_tampering(
    tmp_path,
) -> None:
    shadow = ForexV3ShadowLedger(tmp_path)
    shadow.transaction(lambda state: state.update({"session_date": "2026-09-30"}))
    stored = json.loads(shadow.path.read_text(encoding="utf-8"))
    assert stored["portfolio_id"] == "FOREX_V3_SHADOW_PAPER"
    assert stored["sample_contract_id"] == V3_SHADOW_CONTRACT_ID

    stored["candidate_id"] = "FOREX_BASE_PAPER"
    shadow.path.write_text(json.dumps(stored), encoding="utf-8")

    assert shadow.snapshot()["mode"] == "INVALID"
