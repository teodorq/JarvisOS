"""Fail-closed readiness gate for the latest local Forex research report."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.trading.forex_models import MAJOR_FOREX_PAIRS


_MAJOR_SYMBOLS = frozenset(pair.symbol for pair in MAJOR_FOREX_PAIRS)


class ForexHistoricalResearchGate:
    """Summarize a local report without trusting it to enable execution."""

    MAX_REPORT_BYTES = 20 * 1024 * 1024

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.report_path = (
            self.project_root / "data" / "trading" / "research" / "latest.json"
        )

    def status(self) -> dict[str, Any]:
        unavailable = self._result(
            status="NOT_AVAILABLE",
            blocks=("HISTORICAL_RESEARCH_REPORT_MISSING",),
        )
        try:
            path = self.report_path.resolve(strict=False)
            path.relative_to(self.project_root.resolve(strict=False))
            if not path.is_file():
                return unavailable
            size = path.stat().st_size
            if size <= 0 or size > self.MAX_REPORT_BYTES:
                return self._result(
                    status="INVALID",
                    blocks=("HISTORICAL_RESEARCH_REPORT_INVALID",),
                )
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return self._result(
                status="INVALID",
                blocks=("HISTORICAL_RESEARCH_REPORT_INVALID",),
            )
        if not isinstance(raw, dict) or any(
            raw.get(key) != expected
            for key, expected in (
                ("status", "FOREX_MULTI_PAIR_RESEARCH_COMPLETED"),
                ("mode", "LOCAL_HISTORICAL_RESEARCH_ONLY"),
                ("source_fingerprints_verified", True),
                ("source_quality_ready", True),
                ("portfolio_pln_aggregation_performed", True),
                ("historical_pln_conversion_series_verified", True),
                ("parameter_optimization_performed", False),
                ("automatic_paper_promotion", False),
                ("broker_connection_used", False),
                ("paper_orders_sent", False),
                ("live_orders_sent", False),
            )
        ):
            return self._result(
                status="INVALID",
                blocks=("HISTORICAL_RESEARCH_CONTRACT_INVALID",),
            )
        pairs = raw.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != len(_MAJOR_SYMBOLS):
            return self._result(
                status="INVALID",
                blocks=("HISTORICAL_RESEARCH_PAIR_SET_INVALID",),
            )
        averages: dict[str, Decimal] = {}
        try:
            for item in pairs:
                if not isinstance(item, dict):
                    raise ValueError
                symbol = str(item.get("pair", ""))
                if symbol in averages or symbol not in _MAJOR_SYMBOLS:
                    raise ValueError
                value = Decimal(str(item.get("average_out_of_sample_return_pct", "")))
                if not value.is_finite():
                    raise ValueError
                averages[symbol] = value
        except (InvalidOperation, ValueError):
            return self._result(
                status="INVALID",
                blocks=("HISTORICAL_RESEARCH_PAIR_RESULT_INVALID",),
            )
        if set(averages) != _MAJOR_SYMBOLS:
            return self._result(
                status="INVALID",
                blocks=("HISTORICAL_RESEARCH_PAIR_SET_INVALID",),
            )

        positive = tuple(sorted(
            symbol for symbol, value in averages.items() if value > 0
        ))
        non_positive = tuple(sorted(set(averages) - set(positive)))
        portfolio = raw.get("portfolio")
        checks = portfolio.get("performance_checks") if isinstance(portfolio, dict) else None
        required_checks = {
            "average_return_positive",
            "compounded_return_positive",
            "profitable_window_ratio_met",
            "maximum_drawdown_within_limit",
            "minimum_trade_count_met",
        }
        if (
            not isinstance(portfolio, dict)
            or portfolio.get("status") != "COMPLETED"
            or portfolio.get("account_currency") != "PLN"
            or portfolio.get("portfolio_pln_aggregation_performed") is not True
            or portfolio.get("historical_pln_conversion_series_verified") is not True
            or portfolio.get("position_sizing_matches_paper_coordinator") is not True
            or portfolio.get("take_profit_matches_paper") is not True
            or portfolio.get("broker_connection_used") is not False
            or portfolio.get("paper_orders_sent") is not False
            or portfolio.get("live_orders_sent") is not False
            or not isinstance(checks, dict)
            or set(checks) != required_checks
            or any(type(value) is not bool for value in checks.values())
            or portfolio.get("strategy_performance_validated")
            is not all(checks.values())
        ):
            return self._result(
                status="INVALID",
                blocks=("HISTORICAL_RESEARCH_PORTFOLIO_INVALID",),
            )
        blocks: list[str] = []
        formula_matches = (
            raw.get("stop_loss_formula_matches_paper_coordinator") is True
        )
        sizing_matches = raw.get("position_sizing_matches_paper_coordinator") is True
        take_profit_research_only = raw.get("take_profit_research_only") is True
        take_profit_matches = raw.get("take_profit_matches_paper") is True
        if not formula_matches:
            blocks.append("STOP_LOSS_FORMULA_NOT_MATCHED")
        if not sizing_matches:
            blocks.append("PAPER_POSITION_SIZING_NOT_REPLAYED")
        if take_profit_research_only:
            blocks.append("TAKE_PROFIT_NOT_IMPLEMENTED_IN_PAPER")
        if not take_profit_matches:
            blocks.append("TAKE_PROFIT_NOT_MATCHED")
        if raw.get("strategy_performance_validated") is not True:
            blocks.append("STRATEGY_PERFORMANCE_NOT_VALIDATED")
        return self._result(
            status="READY" if not blocks else "BLOCKED",
            blocks=tuple(blocks),
            source_export_id=str(raw.get("source_export_id", ""))[:96],
            positive_pairs=positive,
            non_positive_pairs=non_positive,
            formula_matches=formula_matches,
            sizing_matches=sizing_matches,
            take_profit_research_only=take_profit_research_only,
            take_profit_matches=take_profit_matches,
        )

    @staticmethod
    def _result(
        *,
        status: str,
        blocks: tuple[str, ...],
        source_export_id: str = "",
        positive_pairs: tuple[str, ...] = (),
        non_positive_pairs: tuple[str, ...] = (),
        formula_matches: bool = False,
        sizing_matches: bool = False,
        take_profit_research_only: bool = False,
        take_profit_matches: bool = False,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "mode": "LOCAL_HISTORICAL_RESEARCH_GATE",
            "source_export_id": source_export_id,
            "positive_average_pair_count": len(positive_pairs),
            "positive_average_pairs": list(positive_pairs),
            "non_positive_average_pairs": list(non_positive_pairs),
            "stop_loss_formula_matches_paper_coordinator": formula_matches,
            "position_sizing_matches_paper_coordinator": sizing_matches,
            "take_profit_research_only": take_profit_research_only,
            "take_profit_matches_paper": take_profit_matches,
            "strategy_candidate_blocks": list(blocks),
            "strategy_candidate_ready": not blocks,
            "automatic_paper_promotion": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        }


__all__ = ["ForexHistoricalResearchGate"]
