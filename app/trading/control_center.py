"""Owner-only readiness view for the JARVIS OS paper-trading foundation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.market_data.forex_environment import ForexDataSettings
from app.trading.backtest import HistoricalPaperBacktester
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.forex_observation import ForexObservationJournal
from app.trading.forex_risk import ForexPaperPolicy
from app.trading.forex_scanner import ForexMarketScanner
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
        self.forex_policy = ForexPaperPolicy()
        self.forex_scanner = ForexMarketScanner()
        self.forex = ForexPaperCoordinator(self.forex_policy)
        self.forex_data = ForexDataSettings.from_environment()
        self.forex_observations = ForexObservationJournal(project_root)

    def status(self) -> dict[str, Any]:
        account = self.engine.status()
        data_readiness = self.forex_data.readiness()
        observations = self.forex_observations.summary()
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
                "multi_pair_forex_scanner": True,
                "forex_currency_portfolio_risk": True,
                "forex_paper_decision_coordinator": True,
                "forex_local_paper_autopilot": True,
                "forex_execution_risk_recheck": True,
                "forex_read_only_data_adapters": True,
                "forex_cross_source_gate": True,
                "forex_event_risk_gate": True,
                "forex_tamper_evident_observation": observations["audit_chain_valid"],
                "kill_switch": True,
                "forex_data_configuration_complete": data_readiness["complete"],
                "external_market_data": False,
                "external_economic_calendar": False,
                "independent_second_price_source": False,
                "live_pln_conversion": False,
                "external_paper_broker": False,
            },
            "forex": {
                "status": "LOCAL_SCANNER_READY",
                "universe": [pair.symbol for pair in MAJOR_FOREX_PAIRS],
                "pair_count": len(MAJOR_FOREX_PAIRS),
                "bidirectional_paper_signals": True,
                "automatic_paper_execution": True,
                "continuous_runtime_active": False,
                "opening_gate_ready": False,
                "data_configuration_complete": data_readiness["complete"],
                "data_configuration": data_readiness,
                "observation": observations,
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
        data = snapshot["forex"]["data_configuration"]
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
            "• Forex: skaner 7 głównych par, ranking i wspólne limity walutowe "
            "— gotowe lokalnie.\n"
            "• Autopilot PAPER: lokalne otwieranie, zamykanie, ponowna kontrola "
            "ryzyka i ochrona przed duplikatem — gotowe.\n"
            f"• Konto demo: {account['equity']} {account['base_currency']}; "
            f"pozycje: {account['position_count']}; wypełnienia: {account['fill_count']}.\n"
            f"• Audyt: {audit}; wyłącznik awaryjny: {kill_switch}.\n"
            "• Dane Forex: lokalny adapter MT5 DEMO, opcjonalny OANDA Practice, "
            "Twelve Data, NBP i publiczny kalendarz Forex Factory oraz kontrola "
            "rozbieżności są gotowe.\n"
            f"• Konfiguracja źródeł: {'kompletna' if data['complete'] else 'oczekuje na lokalne klucze kont demonstracyjnych'}; "
            "automatyczne wejścia pozostają zablokowane do chwili poprawnej kontroli "
            "wszystkich źródeł w bieżącym cyklu.\n"
            "• Sygnały LONG/SHORT istnieją tylko w planie PAPER. Prawdziwe "
            "zlecenia, dźwignia, sieć i dostęp do "
            "pieniędzy: twardo zablokowane.\n"
            "Następny etap: połączyć lokalny MT5 wyłącznie z rachunkiem DEMO, "
            "skonfigurować klucze danych i wykonać serię cykli obserwacyjnych."
        )


__all__ = ["TradingControlCenter"]
