"""Owner-only readiness view for the JARVIS OS paper-trading foundation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.market_data.forex_environment import (
    ForexDataSettings,
    load_forex_environment,
)
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
        self.project_root = resolve_project_root(project_root)
        load_forex_environment(self.project_root)
        self.policy = PaperTradingPolicy()
        self.engine = PaperTradingEngine(self.project_root, policy=self.policy)
        self.risk = PreTradeRiskEngine(self.policy)
        self.backtester = HistoricalPaperBacktester(self.policy)
        self.forex_policy = ForexPaperPolicy()
        self.forex_scanner = ForexMarketScanner()
        self.forex = ForexPaperCoordinator(self.forex_policy)
        self.forex_data = ForexDataSettings.from_environment()
        self.forex_observations = ForexObservationJournal(self.project_root)

    def status(self) -> dict[str, Any]:
        account = self.engine.status()
        data_readiness = self.forex_data.readiness()
        observations = self.forex_observations.summary()
        opening_gate_ready = bool(
            data_readiness["complete"]
            and observations["paper_promotion_ready"]
            and observations["audit_chain_valid"]
        )
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
                "automatic_paper_execution_available": True,
                "automatic_paper_execution": False,
                "continuous_runtime_active": False,
                "opening_gate_ready": opening_gate_ready,
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

    def format_observation_review(self) -> str:
        review = self.forex_observations.review()
        remaining = int(review["remaining_qualified_observations"])
        remaining_days = int(review["remaining_market_days"])
        blocks = review["distributions"]["opening_blocks"]
        actions = review["distributions"]["proposed_instruction_actions"]
        block_text = ", ".join(
            f"{code}: {count}" for code, count in blocks.items()
        ) or "brak"
        action_text = ", ".join(
            f"{action}: {count}" for action, count in actions.items()
        ) or "brak propozycji"
        safety = review["safety"]
        if review["status"] == "READY_FOR_OWNER_REVIEW":
            decision = "GOTOWY DO RĘCZNEGO PRZEGLĄDU; PAPER nadal jest wyłączony"
        elif review["status"] == "BLOCKED":
            decision = "ZABLOKOWANY przez błąd integralności lub bezpieczeństwa"
        else:
            day_word = "dnia rynkowego" if remaining_days == 1 else "dni rynkowych"
            decision = (
                f"ZBIERANIE DANYCH; brakuje {remaining} obserwacji i "
                f"{remaining_days} {day_word}"
            )
        return (
            "Audyt obserwacji Forex JARVIS OS — tylko odczyt:\n"
            f"• Wynik: {decision}.\n"
            f"• Wpisy: {review['observation_count']}; ukończone "
            f"{review['completed_count']}; zablokowane {review['blocked_count']}.\n"
            f"• Kwalifikowane: {review['qualified_market_open_count']}/"
            f"{review['minimum_market_open_observations']}; dni rynkowe "
            f"{review['qualified_market_day_count']}/{review['minimum_market_days']}.\n"
            f"• Przyczyny blokad: {block_text}.\n"
            f"• Proponowane decyzje (niewykonane): {action_text}.\n"
            f"• Audyt: {'prawidłowy' if review['audit_chain_valid'] else 'USZKODZONY'}; "
            f"pokrycie 7 par: {'pełne' if safety['qualified_pair_coverage_complete'] else 'NIEPEŁNE'}.\n"
            f"• Bezpieczeństwo: pozycje {'bez zmian' if safety['all_positions_unchanged'] else 'ZMIENIONE'}; "
            f"zlecenia PAPER: {'wykryte' if safety['paper_orders_detected'] else '0'}; "
            f"zlecenia LIVE: {'wykryte' if safety['live_orders_detected'] else '0'}; "
            f"sieć zleceń: {'wykryta' if safety['order_network_access_detected'] else 'wyłączona'}.\n"
            "• Raport nie może sam uruchomić PAPER ani LIVE."
        )

    def format_status(self) -> str:
        snapshot = self.status()
        account = snapshot["account"]
        data = snapshot["forex"]["data_configuration"]
        observation = snapshot["forex"]["observation"]
        kill_switch = (
            "AKTYWNY — nowe symulowane zlecenia są zatrzymane"
            if account["kill_switch_active"]
            else "gotowy"
        )
        audit = "prawidłowy" if account["audit_chain_valid"] else "USZKODZONY"
        qualified = int(observation["qualified_market_open_count"])
        required = int(observation["minimum_market_open_observations"])
        days = int(observation["qualified_market_day_count"])
        required_days = int(observation["minimum_market_days"])
        remaining = max(0, required - qualified)
        remaining_days = max(0, required_days - days)
        observation_audit = (
            "prawidłowy" if observation["audit_chain_valid"] else "USZKODZONY"
        )
        if not observation["audit_chain_valid"]:
            gate = (
                "ZABLOKOWANA — łańcuch audytu obserwacji jest uszkodzony; "
                "PAPER pozostaje wyłączony"
            )
            next_step = "sprawdzić i naprawić lokalny dziennik obserwacji"
        elif observation["paper_promotion_ready"]:
            gate = (
                "GOTOWA DO PRZEGLĄDU — automatyczna promocja jest wyłączona, "
                "a PAPER nie został uruchomiony"
            )
            next_step = (
                "przejrzeć wyniki obserwacji i dopiero potem jawnie uruchomić "
                "ciągły tryb PAPER"
            )
        else:
            day_word = "dnia rynkowego" if remaining_days == 1 else "dni rynkowych"
            gate = (
                f"ZABLOKOWANA — brakuje {remaining} obserwacji i "
                f"{remaining_days} {day_word}"
            )
            next_step = "pozostawić obserwator włączony do spełnienia obu progów"
        return (
            "Trading JARVIS OS — przygotowanie PAPER ONLY:\n"
            "• Rdzeń: ścisłe modele rynku, walidowany import CSV, backtest bez "
            "podglądania przyszłości i lokalna księga — gotowe.\n"
            "• Ryzyko: limity zlecenia, pozycji, ekspozycji, dziennej straty, "
            "spreadu i liczby zleceń — aktywne.\n"
            "• Forex: skaner 7 głównych par, ranking i wspólne limity walutowe "
            "— gotowe lokalnie.\n"
            "• Silnik autopilota PAPER: lokalne otwieranie, zamykanie, ponowna "
            "kontrola ryzyka i ochrona przed duplikatem — dostępne, lecz wykonanie "
            "pozostaje WYŁĄCZONE.\n"
            f"• Konto demo: {account['equity']} {account['base_currency']}; "
            f"pozycje: {account['position_count']}; wypełnienia: {account['fill_count']}.\n"
            f"• Audyt: {audit}; wyłącznik awaryjny: {kill_switch}.\n"
            f"• Obserwacje Forex: kwalifikowane {qualified}/{required}; dni "
            f"rynkowe {days}/{required_days}; wszystkie wpisy "
            f"{observation['observation_count']}; zablokowane "
            f"{observation['blocked_count']}; audyt {observation_audit}.\n"
            f"• Bramka PAPER: {gate}.\n"
            "• Dane Forex: lokalny adapter MT5 DEMO, opcjonalny OANDA Practice, "
            "Twelve Data, NBP i publiczny kalendarz Forex Factory oraz kontrola "
            "rozbieżności są gotowe.\n"
            f"• Konfiguracja źródeł: {'kompletna' if data['complete'] else 'niekompletna — sprawdź lokalny plik config/forex.env'}; "
            "automatyczne wejścia pozostają zablokowane i wymagają również "
            "ukończenia bramki obserwacji.\n"
            "• Sygnały LONG/SHORT istnieją tylko w planie PAPER. Prawdziwe "
            "zlecenia, dźwignia, sieć i dostęp do "
            "pieniędzy: twardo zablokowane.\n"
            f"Następny etap: {next_step}."
        )


__all__ = ["TradingControlCenter"]
