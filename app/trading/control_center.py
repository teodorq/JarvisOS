"""Owner-only readiness view for the JARVIS OS paper-trading foundation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.market_data.forex_environment import (
    ForexDataSettings,
    load_forex_environment,
)
from app.trading.backtest import HistoricalPaperBacktester
from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_activity import ForexPaperActivityFeed
from app.trading.forex_dashboard import ForexPaperDashboard
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_forward_evidence import (
    ForexV2ForwardEvidenceReport,
    ForexV3ForwardEvidenceReport,
)
from app.trading.forex_forward_review import ForexV2OwnerReviewPacket
from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.forex_observation import ForexObservationJournal
from app.trading.forex_performance_review import (
    ForexPaperPerformanceReviewPacket,
)
from app.trading.forex_research_status import ForexHistoricalResearchGate
from app.trading.forex_risk import ForexPaperPolicy
from app.trading.forex_runtime_summary import ForexRuntimeCycleSummary
from app.trading.forex_scanner import ForexMarketScanner
from app.trading.forex_strategy_cohorts import ForexStrategyCohortReview
from app.trading.forex_v2_research_dashboard import ForexV2ResearchDashboard
from app.trading.forex_v3_shadow import (
    ForexV3ShadowInitializer,
    ForexV3ShadowReadiness,
)
from app.trading.forex_v3_shadow_plan_journal import (
    ForexV3ShadowPlanJournal,
)
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
        self.forex_executor = ForexPaperExecutionEngine(
            self.project_root,
            policy=self.forex_policy,
        )
        self.forex_data = ForexDataSettings.from_environment()
        self.forex_activity = ForexPaperActivityFeed(
            self.project_root,
            settings=self.forex_data,
        )
        self.forex_performance_review = ForexPaperPerformanceReviewPacket(
            self.project_root
        )
        self.forex_observations = ForexObservationJournal(self.project_root)
        self.forex_research = ForexHistoricalResearchGate(self.project_root)
        self.forex_forward_evidence = ForexV2ForwardEvidenceReport(
            self.project_root
        )
        self.forex_v3_forward_evidence = ForexV3ForwardEvidenceReport(
            self.project_root
        )
        self.forex_v3_shadow = ForexV3ShadowReadiness(
            self.project_root,
            forward_evidence=self.forex_v3_forward_evidence,
        )
        self.forex_v3_shadow_initializer = ForexV3ShadowInitializer(
            self.project_root,
            forward_evidence=self.forex_v3_forward_evidence,
        )
        self.forex_v3_shadow_plans = ForexV3ShadowPlanJournal(
            self.project_root
        )
        self.forex_forward_review = ForexV2OwnerReviewPacket(self.project_root)
        self.forex_strategy_cohorts = ForexStrategyCohortReview(
            self.project_root
        )
        self.forex_v2_dashboard = ForexV2ResearchDashboard(
            self.project_root,
            forward_evidence=self.forex_forward_evidence,
            owner_review=self.forex_forward_review,
        )
        self.forex_runtime_summary = ForexRuntimeCycleSummary(self.project_root)
        self.forex_dashboard = ForexPaperDashboard(
            self.project_root,
            executor=self.forex_executor,
            performance_review=self.forex_performance_review,
            v2_research=self.forex_v2_dashboard,
            runtime_summary=self.forex_runtime_summary,
        )

    def status(self) -> dict[str, Any]:
        account = self.engine.status()
        data_readiness = self.forex_data.readiness()
        observations = self.forex_observations.summary()
        research = self.forex_research.status()
        forward_evidence = self.forex_forward_evidence.review()
        v3_forward_evidence = self.forex_v3_forward_evidence.review()
        v3_shadow = self.forex_v3_shadow.status()
        v3_shadow_plans = self.forex_v3_shadow_plans.summary()
        forward_review = self.forex_forward_review.review(forward_evidence)
        forex_account = self.forex_executor.status()
        performance_review = self.forex_performance_review.review(
            forex_account
        )
        strategy_cohorts = self.forex_strategy_cohorts.review()
        runtime_cycle = self._last_runtime_cycle()
        observer_runtime = self._observer_runtime_status()
        opening_gate_ready = bool(
            data_readiness["complete"]
            and observations["paper_promotion_ready"]
            and observations["audit_chain_valid"]
            and research["strategy_candidate_ready"]
        )
        demo_paper_override_active = bool(
            self.forex_data.paper_autopilot_enabled
            and self.forex_data.primary_provider == "MT5_DEMO"
            and data_readiness["complete"]
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
                "chronological_holdout_backtest": True,
                "non_overlapping_walk_forward_backtest": True,
                "validated_historical_csv": True,
                "mt5_demo_closed_m15_history_export": True,
                "historical_dataset_fingerprint_recheck": True,
                "historical_m15_quality_audit": True,
                "forex_historical_strategy_candidate": research[
                    "strategy_candidate_ready"
                ],
                "multi_pair_forex_scanner": True,
                "forex_currency_portfolio_risk": True,
                "forex_paper_decision_coordinator": True,
                "forex_local_paper_autopilot": True,
                "forex_execution_risk_recheck": True,
                "forex_read_only_data_adapters": True,
                "forex_cross_source_gate": True,
                "forex_event_risk_gate": True,
                "forex_tamper_evident_observation": observations["audit_chain_valid"],
                "forex_v2_forward_evidence_report": bool(
                    forward_evidence.get("source_state_valid") is True
                    and not forward_evidence.get("invalid_cycle_count", 0)
                ),
                "forex_v3_forward_evidence_report": bool(
                    v3_forward_evidence.get("source_state_valid") is True
                    and not v3_forward_evidence.get("invalid_cycle_count", 0)
                ),
                "forex_v3_shadow_readiness": bool(
                    v3_shadow.get("status")
                    in {
                        "WAITING_FOR_FORWARD_SAMPLE",
                        "READY_FOR_MANUAL_SHADOW_INITIALIZATION",
                        "SHADOW_INITIALIZED_INACTIVE",
                    }
                    and v3_shadow.get("shadow_execution_enabled") is False
                ),
                "forex_v3_shadow_plan_journal": bool(
                    v3_shadow_plans.get("audit_chain_valid") is True
                    and v3_shadow_plans.get("shadow_execution_enabled")
                    is False
                ),
                "forex_v2_owner_review_packet": bool(
                    forward_review.get("status") == "READY_FOR_OWNER_REVIEW"
                    and forward_review.get("packet_persisted") is True
                    and forward_review.get("review_snapshot_frozen") is True
                ),
                "forex_paper_performance_review_packet": bool(
                    performance_review.get("status")
                    == "READY_FOR_OWNER_REVIEW"
                    and performance_review.get("packet_persisted") is True
                    and performance_review.get("review_snapshot_frozen") is True
                ),
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
                "automatic_paper_execution": demo_paper_override_active,
                "continuous_runtime_configured": (
                    self.forex_data.paper_autopilot_enabled
                ),
                "unvalidated_strategy_demo_override": (
                    demo_paper_override_active
                ),
                "opening_gate_ready": opening_gate_ready,
                "data_configuration_complete": data_readiness["complete"],
                "data_configuration": data_readiness,
                "observation": observations,
                "historical_research": research,
                "v2_forward_evidence": forward_evidence,
                "v3_forward_evidence": v3_forward_evidence,
                "v3_shadow": v3_shadow,
                "v3_shadow_plans": v3_shadow_plans,
                "v2_owner_review": forward_review,
                "paper_account": forex_account,
                "paper_performance_review": performance_review,
                "strategy_cohort_review": strategy_cohorts,
                "last_runtime_cycle": runtime_cycle,
                "observer_runtime": observer_runtime,
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

    def _last_runtime_cycle(self) -> dict[str, Any]:
        """Read a bounded, secret-free summary of the watchdog's last result."""
        return self.forex_runtime_summary.snapshot()

    def _observer_runtime_status(self) -> dict[str, Any]:
        path = self.project_root / "data" / "trading" / "forex_observer_status.json"
        empty = {
            "available": False,
            "status": "NO_HEARTBEAT",
            "checked_at": "",
            "market_window_open": False,
            "mt5_running": False,
            "last_cycle_observed_at": "",
            "protection_interval_seconds": 0,
            "protection_status": "NOT_RUN",
            "protection_checked_at": "",
            "protection_reason": "",
            "protection_consecutive_failure_count": 0,
            "protection_attention_required": False,
            "stale": True,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }
        try:
            if not path.is_file() or not 0 < path.stat().st_size <= 65_536:
                return empty
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                return empty
            checked_at = datetime.fromisoformat(
                str(payload.get("checked_at", "")).replace("Z", "+00:00")
            ).astimezone(timezone.utc)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return empty
        unsafe = any(
            payload.get(key) is not False
            for key in (
                "broker_orders_sent",
                "live_orders_sent",
                "real_money_access",
            )
        )
        age_seconds = max(
            0,
            (datetime.now(timezone.utc) - checked_at).total_seconds(),
        )
        status = str(payload.get("status", "UNKNOWN"))[:80]
        try:
            protection_interval = max(
                0,
                min(300, int(payload.get("protection_interval_seconds", 0))),
            )
            protection_failures = max(
                0,
                min(
                    1_000,
                    int(payload.get(
                        "protection_consecutive_failure_count",
                        0,
                    )),
                ),
            )
        except (TypeError, ValueError):
            protection_interval = 0
            protection_failures = 0
        return {
            "available": True,
            "status": "SAFETY_VIOLATION" if unsafe else status,
            "checked_at": checked_at.isoformat(),
            "market_window_open": payload.get("market_window_open") is True,
            "mt5_running": payload.get("mt5_running") is True,
            "last_cycle_observed_at": str(
                payload.get("last_cycle_observed_at", "")
            )[:64],
            "protection_interval_seconds": protection_interval,
            "protection_status": str(
                payload.get("protection_status", "NOT_RUN")
            )[:80],
            "protection_checked_at": str(
                payload.get("protection_checked_at", "")
            )[:64],
            "protection_reason": str(
                payload.get("protection_reason", "")
            )[:160],
            "protection_consecutive_failure_count": protection_failures,
            "protection_attention_required": bool(
                payload.get("protection_attention_required") is True
                or protection_failures >= 3
            ),
            "stale": age_seconds > 20 * 60,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    def initialize_v3_shadow(self) -> str:
        """Initialize only the empty, non-executing V3 shadow ledger."""
        result = self.forex_v3_shadow_initializer.initialize()
        unsafe = any(
            result.get(key) is not False
            for key in (
                "shadow_execution_enabled",
                "paper_orders_sent",
                "broker_orders_sent",
                "live_orders_sent",
                "network_access",
                "real_money_access",
            )
        )
        if unsafe:
            return (
                "V3 SHADOW: operacja odrzucona przez kontrolę bezpieczeństwa. "
                "Nie utworzono aktywnego portfela ani żadnej pozycji."
            )
        status = str(result.get("status", ""))
        if status == "INITIALIZED_SHADOW_INACTIVE":
            return (
                "V3 SHADOW: utworzono pusty, audytowany portfel porównawczy. "
                "Wykonanie pozostaje wyłączone; nie otwarto żadnej pozycji i "
                "nie wysłano zlecenia."
            )
        if status == "ALREADY_INITIALIZED_SHADOW_INACTIVE":
            return (
                "V3 SHADOW: pusty portfel porównawczy był już przygotowany. "
                "Pozostaje nieaktywny i nie wysyła zleceń."
            )
        reason = str(result.get("reason", ""))[:160]
        if reason == "FORWARD_SAMPLE_INCOMPLETE":
            cycles = result.get("remaining_accepted_cycles", 0)
            cycles = cycles if type(cycles) is int and 0 <= cycles <= 1_000_000 else 0
            days = result.get("remaining_market_days", 0)
            days = days if type(days) is int and 0 <= days <= 1_000_000 else 0
            day_label = "dnia rynkowego" if days == 1 else "dni rynkowych"
            return (
                "V3 SHADOW: próbka nie jest jeszcze kompletna — brakuje "
                f"{cycles} cykli i {days} {day_label}. "
                "Nie utworzono portfela ani pozycji."
            )
        if status == "BLOCKED_EXISTING_SHADOW_LEDGER":
            return (
                "V3 SHADOW: inicjalizacja została zablokowana, ponieważ "
                "istniejąca księga nie przeszła kontroli. Niczego nie zmieniono."
            )
        return (
            "V3 SHADOW: inicjalizacja została bezpiecznie zablokowana "
            f"({reason or 'NIEZNANA_PRZYCZYNA'}). Nie utworzono pozycji ani "
            "nie wysłano zlecenia."
        )

    def format_observation_review(self) -> str:
        review = self.forex_observations.review()
        strict_forward = self.forex_forward_evidence.review()
        strict_v3 = self.forex_v3_forward_evidence.review()
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
        candidate = review["development_candidate_v2"]
        comparison = candidate["signal_comparison"]
        candidate_exclusions = ", ".join(
            f"{code}: {count}"
            for code, count in candidate["exclusion_reasons"].items()
        ) or "brak"
        candidate_issues = ", ".join(
            f"{code}: {count}"
            for code, count in candidate["contract_issues"].items()
        ) or "brak"
        candidate_contract = (
            "prawidłowy" if candidate["evidence_valid"] else "NIEPRAWIDŁOWY"
        )
        strict_exclusions = ", ".join(
            f"{code}: {count}"
            for code, count in strict_forward.get("exclusions", {}).items()
        ) or "brak"
        strict_issues = ", ".join(
            f"{code}: {count}"
            for code, count in strict_forward.get("invalid_issues", {}).items()
        ) or "brak"
        v3_exclusions = ", ".join(
            f"{code}: {count}"
            for code, count in strict_v3.get("exclusions", {}).items()
        ) or "brak"
        v3_issues = ", ".join(
            f"{code}: {count}"
            for code, count in strict_v3.get("invalid_issues", {}).items()
        ) or "brak"
        safety = review["safety"]
        if review["status"] == "READY_FOR_OWNER_REVIEW":
            decision = (
                "GOTOWY DO RĘCZNEGO PRZEGLĄDU; kandydat V2 nie jest "
                "automatycznie awansowany"
            )
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
            f"• Kandydat V2 forward — historyczny scorecard: ważne "
            f"{candidate['valid_forward_observation_count']}/"
            f"{candidate['expected_forward_observation_count']}; odebrane "
            f"{candidate['seen_forward_observation_count']}; wykluczone "
            f"{candidate['excluded_forward_observation_count']} "
            f"({candidate_exclusions}); kontrakt {candidate_contract} "
            f"({candidate_issues}).\n"
            f"• Ścisła próbka V2 od nowego kontraktu: "
            f"{strict_forward.get('accepted_cycle_count', 0)}/"
            f"{strict_forward.get('minimum_accepted_cycle_count', 20)} cykli; "
            f"dni {strict_forward.get('accepted_market_day_count', 0)}/"
            f"{strict_forward.get('minimum_market_day_count', 3)}; "
            f"status {strict_forward.get('status', 'BRAK')}.\n"
            f"• Ścisłe wykluczenia: {strict_exclusions}; błędy: "
            f"{strict_issues}.\n"
            f"• Ścisła próbka V3: "
            f"{strict_v3.get('accepted_cycle_count', 0)}/"
            f"{strict_v3.get('minimum_accepted_cycle_count', 20)} cykli; "
            f"dni {strict_v3.get('accepted_market_day_count', 0)}/"
            f"{strict_v3.get('minimum_market_day_count', 3)}; "
            f"status {strict_v3.get('status', 'BRAK')}; wykluczenia "
            f"{v3_exclusions}; błędy {v3_issues}.\n"
            f"• Filtr V2: sygnały bazowe "
            f"{comparison['base_entry_signal_count']}; zachowane "
            f"{comparison['retained_entry_signal_count']}; odfiltrowane "
            f"{comparison['filtered_entry_signal_count']}; retencja "
            f"{comparison['entry_signal_retention_pct']:.2f}%.\n"
            f"• Audyt: {'prawidłowy' if review['audit_chain_valid'] else 'USZKODZONY'}; "
            f"pokrycie 7 par: {'pełne' if safety['qualified_pair_coverage_complete'] else 'NIEPEŁNE'}.\n"
            f"• Bezpieczeństwo: pozycje {'bez zmian' if safety['all_positions_unchanged'] else 'ZMIENIONE'}; "
            f"zlecenia PAPER: {'wykryte' if safety['paper_orders_detected'] else '0'}; "
            f"zlecenia LIVE: {'wykryte' if safety['live_orders_detected'] else '0'}; "
            f"sieć zleceń: {'wykryta' if safety['order_network_access_detected'] else 'wyłączona'}.\n"
            "• Raport nie może zmienić stanu PAPER/LIVE ani sam awansować V2/V3; "
            "próbka sygnałowa nie potwierdza jeszcze wyniku finansowego."
        )

    def format_status(self) -> str:
        snapshot = self.status()
        forex_account = snapshot["forex"]["paper_account"]
        performance = dict(forex_account.get("performance", {}) or {})
        performance_review_packet = snapshot["forex"][
            "paper_performance_review"
        ]
        performance_integrity = dict(
            performance.get("integrity", {}) or {}
        )
        profit_factor = performance.get("profit_factor")
        profit_factor_text = (
            str(profit_factor) if profit_factor is not None else "n/d"
        )
        performance_evidence = (
            "prawidłowe"
            if performance_integrity.get("evidence_valid") is True
            else "NIEPRAWIDŁOWE"
        )
        pair_review = dict(performance.get("pair_review", {}) or {})
        sample_contract = dict(
            performance.get("sample_contract_review", {}) or {}
        )
        trade_diagnostics = dict(
            performance.get("trade_diagnostics", {}) or {}
        )
        exit_reasons = dict(
            trade_diagnostics.get("exit_reason_counts", {}) or {}
        )
        average_holding = trade_diagnostics.get("average_holding_minutes")
        average_holding_text = (
            f"{average_holding} min" if average_holding is not None else "n/d"
        )
        runtime_cycle = snapshot["forex"]["last_runtime_cycle"]
        observer_runtime = snapshot["forex"]["observer_runtime"]
        data = snapshot["forex"]["data_configuration"]
        observation = snapshot["forex"]["observation"]
        research = snapshot["forex"]["historical_research"]
        forward_evidence = snapshot["forex"]["v2_forward_evidence"]
        v3_forward_evidence = snapshot["forex"]["v3_forward_evidence"]
        v3_shadow = snapshot["forex"]["v3_shadow"]
        v3_shadow_plans = snapshot["forex"]["v3_shadow_plans"]
        forward_review = snapshot["forex"]["v2_owner_review"]
        strategy_cohorts = snapshot["forex"]["strategy_cohort_review"]
        cohort_values = dict(strategy_cohorts.get("cohorts", {}) or {})
        v1_cohort = dict(cohort_values.get("V1_ALL", {}) or {})
        retained_cohort = dict(
            cohort_values.get("V2_RETAINED", {}) or {}
        )
        filtered_cohort = dict(
            cohort_values.get("V2_FILTERED", {}) or {}
        )
        automatic_paper = bool(
            snapshot["forex"]["automatic_paper_execution"]
        )
        autopilot_text = (
            "AKTYWNE W TRYBIE DEMO"
            if automatic_paper
            else "dostępne, lecz wykonanie pozostaje WYŁĄCZONE"
        )
        automatic_entry_text = (
            "automatyczne PAPER: AKTYWNE"
            if automatic_paper
            else (
                "automatyczne wejścia pozostają zablokowane i wymagają również "
                "ukończenia bramki obserwacji"
            )
        )
        if performance_review_packet.get("status") == "READY_FOR_OWNER_REVIEW":
            performance_packet_text = (
                "ZAMROŻONY I GOTOWY DO RĘCZNEGO PRZEGLĄDU; bez automatycznej "
                "zmiany PAPER i bez LIVE"
            )
        elif performance_review_packet.get("status") == "WAITING_FOR_PAPER_SAMPLE":
            performance_packet_text = (
                f"oczekuje na próbkę "
                f"{performance_review_packet.get('valid_closed_trade_count', 0)}/"
                f"{performance_review_packet.get('minimum_closed_trades_for_review', 20)}; "
                "pierwszy pełny wynik zostanie zapisany niezmiennie"
            )
        else:
            performance_packet_text = (
                "ZABLOKOWANY — dowody księgi lub kontraktu próbki są niespójne"
            )
        position_details = "; ".join(
            f"{item['pair'].replace('_', '/')} {item['side']} po {item['entry_price']} "
            f"(SL {item['stop_loss']}, TP {item['take_profit']})"
            for item in forex_account["open_positions"]
        ) or "brak"
        kill_switch = (
            "AKTYWNY — nowe symulowane zlecenia są zatrzymane"
            if forex_account["kill_switch_active"]
            else "gotowy"
        )
        loss_streak_safety = dict(
            forex_account.get("loss_streak_safety", {}) or {}
        )
        loss_streak_text = (
            "PRZERWA W NOWYCH WEJŚCIACH; zamknięcia pozostają aktywne; "
            f"wznowienie {loss_streak_safety.get('resume_at', 'po cooldownie')}"
            if loss_streak_safety.get("active") is True
            else (
                f"gotowy; bieżąca seria strat "
                f"{loss_streak_safety.get('current_consecutive_losses', 0)}/"
                f"{loss_streak_safety.get('threshold', 3)}"
            )
        )
        weekly_loss_safety = dict(
            forex_account.get("weekly_loss_safety", {}) or {}
        )
        weekly_loss_text = (
            "PRZERWA W NOWYCH WEJŚCIACH; zamknięcia pozostają aktywne; "
            f"reset {weekly_loss_safety.get('reset_at', 'w następnym tygodniu')}"
            if weekly_loss_safety.get("active") is True
            else (
                f"gotowy; wynik tygodnia "
                f"{weekly_loss_safety.get('weekly_pnl_pln', '0.00')} PLN; "
                f"pozostały limit straty "
                f"{weekly_loss_safety.get('remaining_loss_capacity_pln', '0.00')} PLN"
            )
        )
        audit = (
            "prawidłowy" if forex_account["audit_chain_valid"] else "USZKODZONY"
        )
        if not runtime_cycle["available"]:
            latest_cycle_text = "brak zapisanego wyniku watchdogu"
        elif runtime_cycle["decision"] == "PAPER_EXECUTED":
            latest_cycle_text = (
                f"wykonano {runtime_cycle['execution_count']} lokalnych operacji PAPER"
            )
        elif runtime_cycle["decision"] == "NO_ENTRY_SIGNAL":
            latest_cycle_text = (
                "brak nowego sygnału wejścia; "
                f"gotowe pary {runtime_cycle['ready_pair_count']}/7"
            )
        elif runtime_cycle["decision"] in {"DATA_BLOCKED", "PAIR_DATA_BLOCKED"}:
            if runtime_cycle["high_impact_event_window"]:
                latest_cycle_text = (
                    "cykl bez nowych transakcji — okno ważnego wydarzenia; "
                    "nowe wejścia PAPER są wstrzymane"
                )
            else:
                reason_text = ", ".join(
                    f"{code}: {count}"
                    for code, count in runtime_cycle["reason_codes"].items()
                ) or "niepełne dane"
                latest_cycle_text = (
                    f"cykl bez transakcji — blokady danych: {reason_text}"
                )
        else:
            latest_cycle_text = "cykl zakończony bez transakcji"
        if not runtime_cycle.get("v3_shadow_observation_available"):
            latest_v3_cycle_text = "brak obserwacji V3 w ostatnim cyklu"
        elif runtime_cycle.get("v3_shadow_safety_valid") is not True:
            latest_v3_cycle_text = (
                "ODRZUCONA — niespójne flagi bezpieczeństwa; wykonanie pozostaje "
                "wyłączone"
            )
        elif (
            runtime_cycle.get("v3_shadow_observation_status")
            == "SHADOW_PLAN_OBSERVED"
        ):
            latest_v3_cycle_text = (
                "zapisano niewykonywalny plan "
                f"{runtime_cycle.get('v3_shadow_decision_status') or 'NO_ACTION'}; "
                f"instrukcje {runtime_cycle.get('v3_shadow_instruction_count', 0)}; "
                "wykonanie wyłączone"
            )
        elif (
            runtime_cycle.get("v3_shadow_observation_status")
            == "SHADOW_PLAN_ALREADY_OBSERVED"
        ):
            latest_v3_cycle_text = (
                "plan z tego cyklu był już zapisany; wykonanie wyłączone"
            )
        elif (
            runtime_cycle.get("v3_shadow_observation_status")
            == "SHADOW_PLAN_OBSERVATION_WAITING"
        ):
            latest_v3_cycle_text = (
                "oczekuje na ukończenie próbki i bezpieczną inicjalizację; "
                "nic nie wykonano"
            )
        elif (
            runtime_cycle.get("v3_shadow_observation_status")
            == "SHADOW_PLAN_OBSERVER_FAILED"
        ):
            latest_v3_cycle_text = (
                "obserwator zgłosił błąd, ale bazowy PAPER działał niezależnie; "
                "nic nie wykonano"
            )
        else:
            latest_v3_cycle_text = (
                "plan nie został zapisany; wykonanie pozostaje wyłączone"
            )
        if not observer_runtime["available"]:
            observer_text = "brak heartbeat; sprawdź zadanie Forex Observer"
        elif observer_runtime["stale"]:
            observer_text = "heartbeat NIEAKTUALNY; observer wymaga sprawdzenia"
        elif observer_runtime["status"] == "MARKET_CLOSED_IDLE":
            observer_text = (
                "aktywny; rynek zamknięty, MT5 uruchomi się automatycznie "
                "w oknie handlowym"
            )
        elif observer_runtime["status"] == "MT5_UNAVAILABLE":
            observer_text = "aktywny, ale MT5 jest chwilowo niedostępny"
        else:
            observer_text = (
                f"aktywny ({observer_runtime['status']}); MT5 "
                f"{'działa' if observer_runtime['mt5_running'] else 'oczekuje'}"
            )
        if observer_runtime["available"] and not observer_runtime["stale"]:
            protection_status = observer_runtime["protection_status"]
            protection_reason = observer_runtime["protection_reason"]
            protection_failures = observer_runtime[
                "protection_consecutive_failure_count"
            ]
            if observer_runtime["protection_attention_required"]:
                protection_text = (
                    "ochrona SL/TP WYMAGA UWAGI — kolejne problemy "
                    f"{protection_failures}; {protection_reason or protection_status}"
                )
            elif protection_status == "NO_PROTECTION_TRIGGER":
                protection_text = "ochrona SL/TP działa; próg nie został osiągnięty"
            elif protection_status == "NO_OPEN_POSITIONS":
                protection_text = "ochrona SL/TP działa; brak otwartej pozycji"
            elif protection_status == "PAPER_PROTECTION_APPLIED":
                protection_text = "ochrona SL/TP zamknęła pozycję PAPER"
            elif protection_status == "PAPER_PROTECTION_BLOCKED":
                protection_text = (
                    "ostatnia kontrola SL/TP została bezpiecznie pominięta"
                    f" ({protection_reason or 'dane chwilowo niedostępne'})"
                )
            else:
                protection_text = "ochrona SL/TP oczekuje na pierwszą kontrolę"
            observer_text = f"{observer_text}; {protection_text}"
        qualified = int(observation["qualified_market_open_count"])
        required = int(observation["minimum_market_open_observations"])
        days = int(observation["qualified_market_day_count"])
        required_days = int(observation["minimum_market_days"])
        remaining = max(0, required - qualified)
        remaining_days = max(0, required_days - days)
        observation_audit = (
            "prawidłowy" if observation["audit_chain_valid"] else "USZKODZONY"
        )
        if forward_review.get("status") == "READY_FOR_OWNER_REVIEW":
            forward_review_text = (
                "GOTOWY DO RĘCZNEGO PRZEGLĄDU — zamrożony, bez zgody na zmianę "
                "PAPER/LIVE i bez potwierdzenia zysku"
            )
        elif (
            forward_review.get("status")
            == "READY_FOR_OWNER_REVIEW_NOT_PERSISTED"
        ):
            forward_review_text = (
                "próg osiągnięty; oczekuje na bezpieczny zapis przez następny "
                "cykl obserwatora"
            )
        elif forward_review.get("status") == "WAITING_FOR_FORWARD_SAMPLE":
            forward_review_text = (
                f"zbieranie próbki {forward_review.get('accepted_cycle_count', 0)}/"
                f"{forward_review.get('minimum_accepted_cycle_count', 20)} "
                "nowych, zweryfikowanych obserwacji; "
                f"dni {forward_review.get('accepted_market_day_count', 0)}/"
                f"{forward_review.get('minimum_market_day_count', 3)}"
            )
            exclusions = forward_evidence.get("exclusions")
            duplicate_count = (
                exclusions.get("DUPLICATE_INPUT_REPLAY", 0)
                if isinstance(exclusions, dict)
                else 0
            )
            if type(duplicate_count) is int and duplicate_count > 0:
                forward_review_text += (
                    "; 1 powtórzony odczyt nie został doliczony"
                    if duplicate_count == 1
                    else f"; {duplicate_count} powtórzone odczyty nie zostały doliczone"
                )
        else:
            forward_review_text = (
                "ZABLOKOWANY — bieżące dowody nie przeszły ścisłej walidacji"
            )
        if forward_review.get("source_report_valid") is True:
            forward_signals = forward_review["signal_comparison"]
            forward_signal_text = (
                f"bazowe {forward_signals['base_entry_signal_count']}; "
                f"V2 zachował {forward_signals['retained_entry_signal_count']}, "
                f"odfiltrował {forward_signals['filtered_entry_signal_count']}"
            )
            if forward_signals["base_entry_signal_count"] == 0:
                forward_signal_text += "; brak sygnałów do porównania"
            elif forward_signals["base_entry_signal_count"] == 1:
                forward_signal_text += (
                    "; tylko jeden przypadek — za mało do oceny działania filtra"
                )
        else:
            forward_signal_text = "niedostępne — dowody zablokowane"
        v3_status = str(v3_forward_evidence.get("status", ""))
        v3_valid = bool(
            v3_forward_evidence.get("source_state_valid") is True
            and v3_forward_evidence.get("invalid_cycle_count", 0) == 0
        )
        if v3_valid:
            v3_cycles = v3_forward_evidence.get("accepted_cycle_count", 0)
            v3_required = v3_forward_evidence.get(
                "minimum_accepted_cycle_count", 20
            )
            v3_days = v3_forward_evidence.get("accepted_market_day_count", 0)
            v3_required_days = v3_forward_evidence.get(
                "minimum_market_day_count", 3
            )
            v3_progress_text = (
                f"próbka minimalna {v3_cycles}/{v3_required}, dni "
                f"{v3_days}/{v3_required_days}; wymaga ręcznej oceny"
                if v3_status == "FORWARD_OBSERVATION_SAMPLE_COMPLETE"
                else f"zbieranie próbki {v3_cycles}/{v3_required}, dni "
                f"{v3_days}/{v3_required_days}"
            )
            v3_exclusions = v3_forward_evidence.get("exclusions")
            v3_duplicate_count = (
                v3_exclusions.get("DUPLICATE_INPUT_REPLAY", 0)
                if isinstance(v3_exclusions, dict)
                else 0
            )
            if type(v3_duplicate_count) is int and v3_duplicate_count > 0:
                v3_progress_text += (
                    "; 1 powtórzony odczyt pominięty"
                    if v3_duplicate_count == 1
                    else f"; {v3_duplicate_count} powtórzone odczyty pominięte"
                )
            v3_signals = dict(
                v3_forward_evidence.get("signal_comparison", {}) or {}
            )
            v3_signal_text = (
                f"bazowe {v3_signals.get('base_entry_signal_count', 0)}; "
                f"V3 zachował {v3_signals.get('retained_entry_signal_count', 0)}, "
                f"odfiltrował {v3_signals.get('filtered_entry_signal_count', 0)}"
            )
        else:
            v3_progress_text = (
                "ZABLOKOWANY — bieżące dowody V3 nie przeszły walidacji"
            )
            v3_signal_text = "niedostępne — dowody zablokowane"
        if v3_shadow.get("status") == "READY_FOR_MANUAL_SHADOW_INITIALIZATION":
            v3_shadow_text = (
                "gotowy do ręcznej inicjalizacji oddzielnej księgi; wykonanie "
                "pozostaje wyłączone"
            )
        elif v3_shadow.get("status") == "SHADOW_INITIALIZED_INACTIVE":
            v3_shadow_text = (
                "oddzielna księga została bezpiecznie zainicjalizowana; jest "
                "pusta, audytowana, a wykonanie pozostaje wyłączone"
            )
        elif v3_shadow.get("status") == "WAITING_FOR_FORWARD_SAMPLE":
            v3_shadow_text = (
                "zablokowany do ukończenia próbki — brakuje "
                f"{v3_shadow.get('remaining_accepted_cycles', 20)} cykli i "
                f"{v3_shadow.get('remaining_market_days', 3)} dni rynkowych; "
                "oddzielna księga nie została jeszcze utworzona"
            )
        else:
            v3_shadow_text = (
                "ZABLOKOWANY — dowody nie pozwalają przygotować oddzielnej księgi"
            )
        if v3_shadow_plans.get("status") == "COLLECTING_SHADOW_PLANS":
            v3_shadow_plans_text = (
                f"zapisane {v3_shadow_plans.get('plan_count', 0)}; plany wejścia "
                f"{v3_shadow_plans.get('entry_plan_count', 0)}, zamknięcia "
                f"{v3_shadow_plans.get('close_plan_count', 0)}, bez działania "
                f"{v3_shadow_plans.get('no_action_plan_count', 0)}; wykonanie "
                "wyłączone; próbka planów "
                f"{v3_shadow_plans.get('plan_count', 0)}/"
                f"{v3_shadow_plans.get('minimum_plan_count', 20)}, dni "
                f"{v3_shadow_plans.get('market_day_count', 0)}/"
                f"{v3_shadow_plans.get('minimum_market_day_count', 3)}; "
                "minimalna kontrola sygnałów wejścia "
                f"{v3_shadow_plans.get('entry_plan_count', 0)}/"
                f"{v3_shadow_plans.get('minimum_entry_plan_count', 3)}"
            )
        elif (
            v3_shadow_plans.get("status")
            == "SHADOW_PLAN_SAMPLE_SIGNAL_SCARCE"
        ):
            v3_shadow_plans_text = (
                "próbka planów kompletna, ale V3 generuje za mało planów "
                f"wejścia: {v3_shadow_plans.get('entry_plan_count', 0)}/"
                f"{v3_shadow_plans.get('minimum_entry_plan_count', 3)}; "
                "przegląd symulacji jest zablokowany, wykonanie wyłączone"
            )
        elif (
            v3_shadow_plans.get("status")
            == "SHADOW_PLAN_SAMPLE_REVIEW_READY"
        ):
            v3_shadow_plans_text = (
                "próbka planów kompletna "
                f"{v3_shadow_plans.get('plan_count', 0)}/"
                f"{v3_shadow_plans.get('minimum_plan_count', 20)}, dni "
                f"{v3_shadow_plans.get('market_day_count', 0)}/"
                f"{v3_shadow_plans.get('minimum_market_day_count', 3)}; "
                f"plany wejścia {v3_shadow_plans.get('entry_plan_count', 0)}, "
                f"zamknięcia {v3_shadow_plans.get('close_plan_count', 0)}, "
                f"bez działania {v3_shadow_plans.get('no_action_plan_count', 0)}; "
                "minimalna częstotliwość sygnałów przeszła kontrolę, ale to nie "
                "jest wynik finansowy i wykonanie pozostaje wyłączone"
            )
        elif (
            v3_shadow_plans.get("status")
            == "WAITING_FOR_FIRST_SHADOW_PLAN"
        ):
            v3_shadow_plans_text = (
                "oczekuje na bezpieczną inicjalizację i pierwszy plan; nie "
                "utworzono żadnej pozycji; próbka planów 0/20, dni 0/3, "
                "plany wejścia 0/3"
            )
        else:
            v3_shadow_plans_text = (
                "ZABLOKOWANY — dziennik planów nie przeszedł kontroli audytu"
            )
        if not observation["audit_chain_valid"]:
            gate = (
                "ZABLOKOWANA — łańcuch audytu obserwacji jest uszkodzony; "
                "PAPER pozostaje wyłączony"
            )
            next_step = "sprawdzić i naprawić lokalny dziennik obserwacji"
        elif (
            observation["paper_promotion_ready"]
            and not research["strategy_candidate_ready"]
        ):
            if automatic_paper:
                gate = (
                    "EKSPERYMENTALNY PAPER DEMO — obserwacje są gotowe, lecz "
                    "strategia historyczna nie spełnia jeszcze progów portfela "
                    "w PLN; LIVE pozostaje zablokowany"
                )
                next_step = (
                    "zbierać wyniki PAPER bez zmiany parametrów, a ocenę "
                    "walk-forward powtórzyć dopiero na nowej próbce"
                )
            else:
                gate = (
                    "ZABLOKOWANA - obserwacje sa gotowe, ale strategia historyczna "
                    "nie spelnia jeszcze progow portfela w PLN"
                )
                next_step = (
                    "ulepszyc strategie bez strojenia pod te same dane, a potem "
                    "powtorzyc walk-forward na nowej probce"
                )
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
            "podglądania przyszłości, chronologiczny holdout, walk-forward i "
            "lokalna księga — gotowe.\n"
            "• Historia: eksport zamkniętych M15 z MT5 DEMO, manifest SHA-256 "
            "oraz kontrola odcisków, synchronizacji, wolumenu i luk — gotowe.\n"
            "• Ryzyko: limity zlecenia, pozycji, ekspozycji, dziennej straty, "
            "spreadu i liczby zleceń — aktywne.\n"
            f"• Bezpiecznik tygodniowy: {weekly_loss_text}.\n"
            f"• Bezpiecznik serii strat: {loss_streak_text}.\n"
            "• Forex: skaner 7 głównych par, ranking i wspólne limity walutowe "
            "— gotowe lokalnie.\n"
            "• Silnik autopilota PAPER: lokalne otwieranie, zamykanie, ponowna "
            f"kontrola ryzyka i ochrona przed duplikatem — {autopilot_text}.\n"
            f"• Konto PAPER Forex: {forex_account['equity_pln']} PLN; "
            f"wynik zrealizowany: {forex_account['realized_pnl_pln']} PLN; "
            f"pozycje: {forex_account['position_count']}; zamknięte transakcje: "
            f"{forex_account['closed_trade_count']}.\n"
            f"• Jakość PAPER: próbka "
            f"{performance.get('valid_closed_trade_count', 0)}/"
            f"{performance.get('minimum_closed_trades_for_review', 20)}; "
            f"średni wynik "
            f"{performance.get('average_trade_pnl_pln', '0.00')} PLN; "
            f"profit factor {profit_factor_text}; maks. obsunięcie zamkniętych "
            f"{performance.get('maximum_closed_trade_drawdown_pln', '0.00')} PLN "
            f"({performance.get('maximum_closed_trade_drawdown_pct', '0.00')}%); "
            f"najdłuższa seria strat "
            f"{performance.get('maximum_consecutive_losses', 0)}; "
            f"dowody {performance_evidence}.\n"
            f"• Zamrożony pakiet wyniku PAPER: {performance_packet_text}.\n"
            f"• Cykl życia próbki: średni czas {average_holding_text}; "
            f"SL {exit_reasons.get('stop_loss', 0)}, "
            f"TP {exit_reasons.get('take_profit', 0)}, "
            f"sygnał/reguła {exit_reasons.get('strategy', 0)}, "
            f"bez powodu {exit_reasons.get('unspecified', 0)}.\n"
            f"• Próbki par: do ręcznego przeglądu "
            f"{pair_review.get('ready_pair_count', 0)}/7; w trakcie "
            f"{pair_review.get('collecting_pair_count', 0)}; bez zamkniętej "
            f"transakcji {pair_review.get('unobserved_pair_count', 7)}; "
            "automatyczny wybór par jest wyłączony.\n"
            f"• Kontrakt próbki: bieżąca wersja "
            f"{sample_contract.get('current_contract_closed_trade_count', 0)}/"
            f"{performance.get('minimum_closed_trades_for_review', 20)}; "
            f"starsze bez odcisku "
            f"{sample_contract.get('legacy_unversioned_closed_trade_count', 0)}; "
            f"obce odciski "
            f"{sample_contract.get('foreign_contract_closed_trade_count', 0)}; "
            f"poprzedni kontrakt "
            f"{sample_contract.get('superseded_contract_closed_trade_count', 0)}; "
            "automatyczne łączenie próbek jest wyłączone.\n"
            f"• Kohorty V1/V2: faktyczny V1 — sygnały "
            f"{v1_cohort.get('open_signal_count', 0)}, zamknięte "
            f"{v1_cohort.get('closed_trade_count', 0)}, wynik "
            f"{v1_cohort.get('net_realized_pnl_pln', '0.00')} PLN; "
            f"V2 zachował {retained_cohort.get('open_signal_count', 0)} "
            f"(zamknięte {retained_cohort.get('closed_trade_count', 0)}, "
            f"wynik {retained_cohort.get('net_realized_pnl_pln', '0.00')} PLN); "
            f"V2 odfiltrował {filtered_cohort.get('open_signal_count', 0)} "
            f"(zamknięte {filtered_cohort.get('closed_trade_count', 0)}, "
            f"wynik {filtered_cohort.get('net_realized_pnl_pln', '0.00')} PLN).\n"
            f"• Otwarte pozycje PAPER: {position_details}.\n"
            f"• Cykle autopilota: {forex_account['processed_cycle_count']}; "
            f"ostatnia decyzja: {latest_cycle_text}.\n"
            f"• Ostatni cykl V3 SHADOW: {latest_v3_cycle_text}.\n"
            f"• Observer Forex: {observer_text}.\n"
            f"• Audyt: {audit}; wyłącznik awaryjny: {kill_switch}.\n"
            f"• Obserwacje Forex: kwalifikowane {qualified}/{required}; dni "
            f"rynkowe {days}/{required_days}; wszystkie wpisy "
            f"{observation['observation_count']}; zablokowane "
            f"{observation['blocked_count']}; audyt {observation_audit}.\n"
            f"• Pakiet przeglądu Forex V2: {forward_review_text}.\n"
            f"• Forward V2 — sygnały wejścia: {forward_signal_text}; "
            "to nie jest wynik finansowy.\n"
            f"• Forward V3: {v3_progress_text}.\n"
            f"• Forward V3 — sygnały wejścia: {v3_signal_text}; "
            "bez automatycznej zmiany PAPER/LIVE.\n"
            f"• Portfel V3 SHADOW: {v3_shadow_text}.\n"
            f"• Dziennik planów V3 SHADOW: {v3_shadow_plans_text}.\n"
            f"• Bramka PAPER: {gate}.\n"
            "• Dane Forex: lokalny adapter MT5 DEMO, opcjonalny OANDA Practice, "
            "Twelve Data, NBP i publiczny kalendarz Forex Factory oraz kontrola "
            "rozbieżności są gotowe.\n"
            f"• Konfiguracja źródeł: {'kompletna' if data['complete'] else 'niekompletna — sprawdź lokalny plik config/forex.env'}; "
            f"{automatic_entry_text}.\n"
            "• Sygnały LONG/SHORT istnieją tylko w planie PAPER. Prawdziwe "
            "zlecenia, dźwignia, sieć i dostęp do "
            "pieniędzy: twardo zablokowane.\n"
            f"Następny etap: {next_step}."
        )


__all__ = ["TradingControlCenter"]
