"""Broker-neutral, local-only paper-trading foundation for JARVIS OS."""

from app.trading.backtest import HistoricalPaperBacktester
from app.trading.control_center import TradingControlCenter
from app.trading.dataset import HistoricalCsvLoader, HistoricalDataset
from app.trading.forex_coordinator import ForexPaperCoordinator, ForexPaperInstruction
from app.trading.forex_candidate_v2 import (
    ForexRegimeCandidatePolicy,
    ForexRegimeFilteredScanner,
)
from app.trading.forex_autopilot import ForexPaperAutopilot
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_historical import (
    BidirectionalForexHistoricalBacktester,
    FixedForexCrossoverSignalGenerator,
    ForexHistoricalPolicy,
    ForexHistoricalSignal,
    ForexHistoricalWalkForwardValidator,
    ForexWalkForwardPolicy,
)
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_portfolio_historical import (
    ForexPortfolioHistoricalBacktester,
    ForexPortfolioHistoricalPolicy,
    ForexPortfolioHistoricalWalkForwardValidator,
    ForexPortfolioWalkForwardPolicy,
)
from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
    major_pair,
)
from app.trading.forex_risk import (
    ForexPaperPolicy,
    ForexPortfolioRiskEngine,
    ForexRateBook,
    ForexRiskDecision,
)
from app.trading.forex_research_status import ForexHistoricalResearchGate
from app.trading.forex_scanner import (
    ForexMarketScanner,
    ForexPairAssessment,
    ForexScannerPolicy,
)
from app.trading.ledger import PaperTradingLedger
from app.trading.models import (
    MarketBar,
    MarketQuote,
    PaperOrder,
    StrategySignal,
    TradingValidationError,
)
from app.trading.paper_broker import LiveTradingBlockedError, PaperTradingEngine
from app.trading.policy import PaperTradingPolicy
from app.trading.risk import PreTradeRiskEngine, RiskDecision
from app.trading.walk_forward import (
    ChronologicalHoldoutValidator,
    HistoricalWalkForwardValidator,
    WalkForwardPolicy,
)

__all__ = [
    "HistoricalPaperBacktester",
    "BidirectionalForexHistoricalBacktester",
    "ChronologicalHoldoutValidator",
    "HistoricalWalkForwardValidator",
    "HistoricalCsvLoader",
    "HistoricalDataset",
    "ForexBar",
    "FixedForexCrossoverSignalGenerator",
    "ForexHistoricalPolicy",
    "ForexHistoricalSignal",
    "ForexHistoricalWalkForwardValidator",
    "ForexHistoricalResearchGate",
    "ForexMarketScanner",
    "ForexPair",
    "ForexPairAssessment",
    "ForexPaperCoordinator",
    "ForexPaperAutopilot",
    "ForexPaperExecutionEngine",
    "ForexPaperInstruction",
    "ForexPaperLedger",
    "ForexPaperPolicy",
    "ForexPortfolioRiskEngine",
    "ForexPortfolioHistoricalBacktester",
    "ForexPortfolioHistoricalPolicy",
    "ForexPortfolioHistoricalWalkForwardValidator",
    "ForexPortfolioWalkForwardPolicy",
    "ForexPosition",
    "ForexQuote",
    "ForexRateBook",
    "ForexRegimeCandidatePolicy",
    "ForexRegimeFilteredScanner",
    "ForexRiskDecision",
    "ForexSafetyContext",
    "ForexScannerPolicy",
    "ForexWalkForwardPolicy",
    "LiveTradingBlockedError",
    "MarketBar",
    "MarketQuote",
    "MAJOR_FOREX_PAIRS",
    "PaperOrder",
    "PaperTradingEngine",
    "PaperTradingLedger",
    "PaperTradingPolicy",
    "PreTradeRiskEngine",
    "RiskDecision",
    "StrategySignal",
    "TradingControlCenter",
    "TradingValidationError",
    "USD_PLN_CONVERSION_PAIR",
    "major_pair",
    "WalkForwardPolicy",
]
