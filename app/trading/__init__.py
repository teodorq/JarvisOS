"""Broker-neutral paper trading with a lazy public import surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_MODULE_EXPORTS = {
    "app.trading.backtest": ("HistoricalPaperBacktester",),
    "app.trading.control_center": ("TradingControlCenter",),
    "app.trading.dataset": ("HistoricalCsvLoader", "HistoricalDataset"),
    "app.trading.forex_coordinator": (
        "ForexPaperCoordinator", "ForexPaperInstruction",
    ),
    "app.trading.forex_activity": ("ForexPaperActivityFeed",),
    "app.trading.forex_activity_journal": ("ForexPaperActivityJournal",),
    "app.trading.forex_dashboard": ("ForexPaperDashboard",),
    "app.trading.forex_candidate_v2": (
        "ForexRegimeCandidatePolicy", "ForexRegimeFilteredScanner",
    ),
    "app.trading.forex_candidate_v3": (
        "ForexStrengthCandidatePolicy", "ForexStrengthFilteredScanner",
    ),
    "app.trading.forex_autopilot": ("ForexPaperAutopilot",),
    "app.trading.forex_executor": ("ForexPaperExecutionEngine",),
    "app.trading.forex_forward_evidence": (
        "ForexV2ForwardEvidenceReport", "ForexV3ForwardEvidenceReport",
        "build_forex_v2_forward_evidence_report",
        "build_forex_v3_forward_evidence_report",
        "verify_forex_v2_forward_evidence_report",
        "verify_forex_v3_forward_evidence_report",
    ),
    "app.trading.forex_forward_review": (
        "ForexV2OwnerReviewPacket", "build_forex_v2_owner_review_packet",
        "verify_forex_v2_owner_review_lineage",
        "verify_forex_v2_owner_review_packet",
    ),
    "app.trading.forex_historical": (
        "BidirectionalForexHistoricalBacktester",
        "FixedForexCrossoverSignalGenerator", "ForexHistoricalPolicy",
        "ForexHistoricalSignal", "ForexHistoricalWalkForwardValidator",
        "ForexWalkForwardPolicy",
    ),
    "app.trading.forex_ledger": ("ForexPaperLedger",),
    "app.trading.forex_paper_performance": (
        "ForexPaperPerformancePolicy", "build_forex_paper_performance_review",
    ),
    "app.trading.forex_performance_review": (
        "ForexPaperPerformanceReviewPacket",
        "build_forex_paper_performance_review_packet",
        "verify_forex_paper_performance_review_lineage",
        "verify_forex_paper_performance_review_packet",
    ),
    "app.trading.forex_portfolio_historical": (
        "ForexPortfolioHistoricalBacktester",
        "ForexPortfolioHistoricalPolicy",
        "ForexPortfolioHistoricalWalkForwardValidator",
        "ForexPortfolioWalkForwardPolicy",
    ),
    "app.trading.forex_models": (
        "ForexBar", "ForexPair", "ForexPosition", "ForexQuote",
        "ForexSafetyContext", "MAJOR_FOREX_PAIRS", "USD_PLN_CONVERSION_PAIR",
        "major_pair",
    ),
    "app.trading.forex_risk": (
        "ForexPaperPolicy", "ForexPortfolioRiskEngine", "ForexRateBook",
        "ForexRiskDecision",
    ),
    "app.trading.forex_research_status": ("ForexHistoricalResearchGate",),
    "app.trading.forex_scanner": (
        "ForexMarketScanner", "ForexPairAssessment", "ForexScannerPolicy",
    ),
    "app.trading.forex_sample_contract": (
        "build_forex_paper_sample_contract",
        "build_forex_v3_shadow_sample_contract", "is_superseded_sample_contract",
        "sample_contracts_match", "verify_forex_paper_sample_contract",
        "verify_forex_v3_shadow_sample_contract",
    ),
    "app.trading.forex_strategy_cohorts": (
        "ForexStrategyCohortReview", "build_forex_strategy_cohort_review",
    ),
    "app.trading.forex_strategy_replay": (
        "ForexStrategyCounterfactualReplay",
    ),
    "app.trading.forex_strategy_walk_forward": (
        "ForexStrategyCounterfactualWalkForwardComparison",
    ),
    "app.trading.forex_trade_diagnostics": ("build_forex_trade_diagnostics",),
    "app.trading.forex_v3_shadow": (
        "ForexV3ShadowInitializer", "ForexV3ShadowReadiness",
    ),
    "app.trading.forex_v3_shadow_ledger": ("ForexV3ShadowLedger",),
    "app.trading.forex_v3_shadow_planner": (
        "ForexV3ShadowPlanner", "verify_forex_v3_shadow_plan",
    ),
    "app.trading.forex_v3_shadow_plan_journal": (
        "ForexV3ShadowPlanJournal",
    ),
    "app.trading.forex_v3_shadow_plan_observer": (
        "ForexV3ShadowPlanObserver",
    ),
    "app.trading.forex_v3_shadow_simulation": (
        "ForexV3ShadowSimulationReadiness",
    ),
    "app.trading.forex_risk_diagnostics": ("build_forex_risk_diagnostics",),
    "app.trading.ledger": ("PaperTradingLedger",),
    "app.trading.models": (
        "MarketBar", "MarketQuote", "PaperOrder", "StrategySignal",
        "TradingValidationError",
    ),
    "app.trading.paper_broker": (
        "LiveTradingBlockedError", "PaperTradingEngine",
    ),
    "app.trading.policy": ("PaperTradingPolicy",),
    "app.trading.risk": ("PreTradeRiskEngine", "RiskDecision"),
    "app.trading.walk_forward": (
        "ChronologicalHoldoutValidator", "HistoricalWalkForwardValidator",
        "WalkForwardPolicy",
    ),
}

_ALIASES = {
    "FOREX_PAPER_SAMPLE_CONTRACT_ID": (
        "app.trading.forex_sample_contract", "CONTRACT_ID",
    ),
    "FOREX_V3_SHADOW_SAMPLE_CONTRACT_ID": (
        "app.trading.forex_sample_contract", "V3_SHADOW_CONTRACT_ID",
    ),
}

_EXPORTS = {
    name: (module_name, name)
    for module_name, names in _MODULE_EXPORTS.items()
    for name in names
}
_EXPORTS.update(_ALIASES)
__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
