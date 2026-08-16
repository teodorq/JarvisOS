"""Owner-only readiness view for the JARVIS OS paper-trading foundation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.trading.backtest import HistoricalPaperBacktester
from app.trading.paper_broker import PaperTradingEngine
from app.trading.policy import PaperTradingPolicy
from app.trading.risk import PreTradeRiskEngine


class TradingControlCenter:
    """Expose a local, secret-free trading readiness snapshot."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.policy = PaperTradingPolicy()
        self.engine = PaperTradingEngine(project_root, policy=self.policy)
        self.risk = PreTradeRiskEngine(self.policy)
        self.backtester = HistoricalPaperBacktester(self.policy)

    def status(self) -> dict[str, Any]:
        account = self.engine.status()
        return {
            "status": "PAPER_FOUNDATION_READY",
            "mode": "PAPER_ONLY",
            "components": {
                "strict_market_models": True,
                "pre_trade_risk": True,
                "atomic_ledger": True,
                "tamper_evident_audit": account["audit_chain_valid"],
                "next_bar_backtest": True,
                "validated_historical_csv": True,
                "kill_switch": True,
                "external_market_data": False,
                "external_paper_broker": False,
            },
            "account": account,
            "limits": self.policy.status(),
            "safety": {
                "live_trading_enabled": False,
                "network_access": False,
                "short_selling_enabled": False,
                "leverage_enabled": False,
                "real_money_access": False,
            },
        }

    def format_status(self) -> str:
        snapshot = self.status()
        account = snapshot["account"]
        kill_switch = (
            "AKTYWNY — nowe symulowane zlecenia są zatrzymane"
            if account["kill_switch_active"]
            else "gotowy"
        )
        audit = "prawidłowy" if account["audit_chain_valid"] else "USZKODZONY"
        return (
            "Trading JARVIS OS — przygotowanie PAPER ONLY:\n"
            "• Rdzeń: ścisłe modele rynku, walidowany import CSV, backtest bez "
            "podglądania przyszłości i lokalna księga — gotowe.\n"
            "• Ryzyko: limity zlecenia, pozycji, ekspozycji, dziennej straty, "
            "spreadu i liczby zleceń — aktywne.\n"
            f"• Konto demo: {account['equity']} {account['base_currency']}; "
            f"pozycje: {account['position_count']}; wypełnienia: {account['fill_count']}.\n"
            f"• Audyt: {audit}; wyłącznik awaryjny: {kill_switch}.\n"
            "• Dane rynkowe i zewnętrzny broker demonstracyjny: jeszcze niepodłączone.\n"
            "• Prawdziwe zlecenia, short selling, dźwignia, sieć i dostęp do "
            "pieniędzy: twardo zablokowane.\n"
            "Następny etap: wybrać klasę aktywów i brokera demonstracyjnego, "
            "a potem przeprowadzić długie testy paper."
        )


__all__ = ["TradingControlCenter"]
