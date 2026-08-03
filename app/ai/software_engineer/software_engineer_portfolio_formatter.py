from __future__ import annotations

from typing import Any


def format_multi_campaign_response(response: dict[str, Any]) -> str:
    portfolio = response.get("portfolio", {})
    status = str(response.get("status", "UNKNOWN"))
    portfolio_id = str(
        response.get(
            "portfolio_id",
            portfolio.get("portfolio_id", "") if isinstance(portfolio, dict) else "",
        )
    )
    campaigns_count = int(
        response.get(
            "campaigns_count",
            len(portfolio.get("campaigns", [])) if isinstance(portfolio, dict) else 0,
        )
        or 0
    )
    completed = int(
        response.get(
            "completed_campaigns",
            len(portfolio.get("completed_campaign_ids", []))
            if isinstance(portfolio, dict)
            else 0,
        )
        or 0
    )
    failed = int(response.get("failed_campaigns", 0) or 0)
    blocked = int(response.get("blocked_campaigns", 0) or 0)
    recent = response.get("portfolios", [])
    lines = [
        f"Autonomous Software Engineer: {status}",
        f"Portfolio kampanii: {portfolio_id or 'brak'}",
        f"Postęp kampanii: {completed}/{campaigns_count}",
    ]
    if isinstance(recent, list) and recent:
        lines.append(f"Ostatnie portfolio: {len(recent)}")
        lines.extend(
            "- "
            + str(item.get("portfolio_id", "brak"))
            + ": "
            + str(item.get("status", "UNKNOWN"))
            for item in recent[:5]
            if isinstance(item, dict)
        )
    if failed:
        lines.append(f"Nieudane kampanie: {failed}")
    if blocked:
        lines.append(f"Zablokowane kampanie: {blocked}")
    if isinstance(portfolio, dict):
        current = str(portfolio.get("current_campaign_id", "")).strip()
        if current:
            lines.append(f"Bieżąca kampania: {current}")
        order = portfolio.get("execution_order", [])
        if isinstance(order, list) and order:
            lines.append("Kolejność: " + " -> ".join(str(item) for item in order))
        risk = portfolio.get("metadata", {}).get("estimated_risk")
        if risk is not None:
            lines.append(f"Szacowane ryzyko: {risk}/10")
    optimization = response.get("optimization", {})
    if not isinstance(optimization, dict) or not optimization:
        optimization = (
            portfolio.get("metadata", {}).get("optimization", {})
            if isinstance(portfolio, dict)
            else {}
        )
    if isinstance(optimization, dict) and optimization:
        score = optimization.get("average_score")
        if score is not None:
            lines.append(f"Wynik optymalizacji: {score}/100")
        selected = optimization.get("selected_campaign_ids", [])
        if isinstance(selected, list) and selected:
            lines.append("Wybrane kampanie: " + ", ".join(str(item) for item in selected[:8]))
        deferred = optimization.get("deferred_campaigns", [])
        if isinstance(deferred, list) and deferred:
            lines.append(f"Odroczone kampanie: {len(deferred)}")
        minutes = optimization.get("estimated_minutes")
        if minutes is not None:
            lines.append(f"Szacowany czas: {minutes} min")
    director = response.get("director_run", {})
    if isinstance(director, dict) and director:
        lines.append(f"Dyrektor kampanii: {director.get('run_id', 'brak')}")
        lines.append(f"Cykle dyrektora: {director.get('cycles', 0)}")
        lines.append(f"Retry dyrektora: {director.get('retries', 0)}")
    director_runs = response.get("director_runs", [])
    if isinstance(director_runs, list) and director_runs:
        lines.append(f"Ostatnie przebiegi dyrektora: {len(director_runs)}")
    report_path = str(response.get("report_path", "")).strip()
    if report_path:
        lines.append(f"Raport portfolio: {report_path}")
    errors = response.get("errors", [])
    if isinstance(errors, list) and errors:
        lines.append("Błędy: " + "; ".join(str(item) for item in errors[-5:]))
    return "\n".join(lines)
