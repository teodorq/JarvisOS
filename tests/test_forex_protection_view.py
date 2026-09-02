from app.gui.forex_protection_view import forex_protection_view


def _value(**changes):
    result = {
        "available": True,
        "status": "NO_PROTECTION_TRIGGER",
        "reason": "",
        "consecutive_failure_count": 0,
        "attention_required": False,
        "stale": False,
        "market_window_open": True,
    }
    result.update(changes)
    return result


def test_protection_view_distinguishes_healthy_attention_and_closed_market() -> None:
    assert forex_protection_view(_value())[:2] == (
        "OCHRONA: DZIAŁA",
        "healthy",
    )
    attention = forex_protection_view(_value(
        status="PAPER_PROTECTION_BLOCKED",
        reason="MT5_PROTECTION_DATA_STALE",
        consecutive_failure_count=3,
        attention_required=True,
    ))
    assert attention[:2] == ("OCHRONA: UWAGA", "danger")
    assert "licznik 3" in attention[2]
    assert forex_protection_view(_value(
        market_window_open=False,
    ))[0] == "OCHRONA: RYNEK ZAMKNIĘTY"


def test_protection_view_handles_missing_stale_and_single_skip() -> None:
    assert forex_protection_view(None)[0] == "OCHRONA: BRAK STATUSU"
    assert forex_protection_view(_value(stale=True))[0] == (
        "OCHRONA: NIEAKTUALNA"
    )
    assert forex_protection_view(_value(
        status="PAPER_PROTECTION_BLOCKED",
        consecutive_failure_count=1,
    ))[0] == "OCHRONA: PONOWI PRÓBĘ"


def test_protection_view_explains_recent_safe_recovery() -> None:
    resumed = forex_protection_view(_value(
        status="NO_OPEN_POSITIONS",
        recent_recovery=True,
        last_recovery_gap_seconds=77_100,
    ))

    assert resumed[:2] == ("OCHRONA: WZNOWIONA", "healthy")
    assert "21 godz. 25 min" in resumed[2]
    assert "przed nowym cyklem" in resumed[2]


def test_protection_view_explains_conservative_m1_replay() -> None:
    replayed = forex_protection_view(_value(
        status="NO_OPEN_POSITIONS",
        recent_recovery_replay=True,
        last_recovery_replay_exit_count=1,
        last_recovery_replay_ambiguous_count=1,
    ))

    assert replayed[:2] == ("OCHRONA: ODTWORZONA", "healthy")
    assert "minutowych świec" in replayed[2]
    assert "konserwatywnie SL" in replayed[2]
