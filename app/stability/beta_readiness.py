from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.stability.common import bounded, utc_iso


class BusinessBetaReadinessCenter:
    """B115 auditable beta gates; no automatic publication or deployment."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.project_root / "data" / "stability" / "business_beta.json",
            lambda: {"audits": [], "confirmations": []},
        )

    def audit(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        gates = [
            self._gate("REAL_SCENARIOS", snapshot.get("scenario_status") == "PASSED"),
            self._gate("PERFORMANCE_SCORE", int(snapshot.get("performance_score", 0)) >= 80),
            self._gate("NO_OPEN_INCIDENTS", int(snapshot.get("open_incidents", 0)) == 0),
            self._gate("RESTART_STATE_RESTORED", bool(snapshot.get("restart_restored"))),
            self._gate("SAFE_DEFAULTS", bool(snapshot.get("safe_defaults"))),
        ]
        passed = sum(item["passed"] for item in gates)
        audit = {
            "audit_id": uuid4().hex[:16],
            "created_at": utc_iso(),
            "status": "PASSED" if passed == len(gates) else "BLOCKED",
            "passed": passed,
            "total": len(gates),
            "gates": gates,
        }
        state = self.store.load()
        state["audits"] = bounded(list(state.get("audits", [])) + [audit], 40)
        self.store.save(state)
        return audit

    def confirm(self) -> dict[str, Any]:
        state = self.store.load()
        audits = list(state.get("audits", []))
        if not audits or audits[-1].get("status") != "PASSED":
            raise ValueError("B115: bramki Business Beta nie są jeszcze zaliczone.")
        confirmation = {
            "confirmation_id": uuid4().hex[:16],
            "audit_id": audits[-1]["audit_id"],
            "status": "BUSINESS_BETA_READY",
            "confirmed_at": utc_iso(),
            "automatic_publication": False,
        }
        state["confirmations"] = bounded(list(state.get("confirmations", [])) + [confirmation], 20)
        self.store.save(state)
        self._export(audits[-1], confirmation)
        return confirmation

    def status(self) -> dict[str, Any]:
        state = self.store.load()
        audits = list(state.get("audits", []))
        confirmations = list(state.get("confirmations", []))
        latest_audit = dict(audits[-1]) if audits else {}
        latest_confirmation = dict(confirmations[-1]) if confirmations else {}
        return {
            "status": "BUSINESS_BETA_READINESS_READY",
            "audit_count": len(audits),
            "latest_audit_status": latest_audit.get("status", "NOT_RUN"),
            "gates_passed": latest_audit.get("passed", 0),
            "gates_total": latest_audit.get("total", 5),
            "beta_ready": latest_confirmation.get("status") == "BUSINESS_BETA_READY",
            "latest_audit": latest_audit,
            "latest_confirmation": latest_confirmation,
        }

    def _export(self, audit: dict[str, Any], confirmation: dict[str, Any]) -> None:
        reports = self.project_root / "AI_PLIKI" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        payload = {"audit": audit, "confirmation": confirmation}
        target = reports / "JARVIS_BUSINESS_BETA_READINESS.json"
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        text = [
            "JARVIS OS BETA READINESS",
            f"Status: {confirmation['status']}",
            f"Audit: {audit['passed']}/{audit['total']}",
            "Automatyczna publikacja: NIE",
        ]
        (reports / "JARVIS_BUSINESS_BETA_READINESS.txt").write_text("\n".join(text) + "\n", encoding="utf-8")

    @staticmethod
    def _gate(name: str, passed: bool) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed)}
