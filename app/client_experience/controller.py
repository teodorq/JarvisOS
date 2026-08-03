from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from app.business.business_config import BusinessConfigStore
from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.stability.beta_readiness import BusinessBetaReadinessCenter


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClientExperienceController:
    """B116-B120 local client shell, first-run setup and Stable gates."""

    STAGES = {
        "B116": "CLIENT_MODE_READY",
        "B117": "ANIMATED_HALO_READY",
        "B118": "FIRST_RUN_SETUP_READY",
        "B119": "USABILITY_VALIDATION_READY",
        "B120": "BUSINESS_1_1_STABLE_GATE_READY",
    }
    HALO_STATES = (
        "idle", "listening", "thinking", "acting",
        "success", "warning", "error",
    )

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.project_root / "data" / "client_experience" / "state.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "profile": {
                "display_name": "Kacper",
                "voice_enabled": True,
                "interaction_mode": "VOICE_AND_TEXT",
                "setup_completed": False,
                "setup_completed_at": "",
            },
            "runtime": {
                "mode": "OWNER",
                "halo_state": "idle",
                "message": "Gotowy, gdy mnie potrzebujesz.",
                "updated_at": "",
            },
            "usability_audits": [],
            "stable_confirmations": [],
        }

    def configure(
        self,
        *,
        display_name: object,
        voice_enabled: bool,
        interaction_mode: object,
    ) -> dict[str, Any]:
        state = self._load()
        profile = dict(state.get("profile", {}) or {})
        profile.update({
            "display_name": self._clean_name(display_name),
            "voice_enabled": bool(voice_enabled),
            "interaction_mode": self._interaction_mode(interaction_mode),
            "setup_completed": True,
            "setup_completed_at": utc_now(),
        })
        state["profile"] = profile
        state["runtime"] = {
            **dict(state.get("runtime", {}) or {}),
            "mode": "CLIENT",
            "halo_state": "idle",
            "message": f"Witaj {profile['display_name']}. Jestem gotowy.",
            "updated_at": utc_now(),
        }
        self.store.save(state)
        return profile

    def set_mode(self, mode: object) -> str:
        value = str(mode or "OWNER").strip().upper()
        if value not in {"CLIENT", "OWNER"}:
            raise ValueError("B120: dozwolony tryb to CLIENT albo OWNER.")
        state = self._load()
        runtime = dict(state.get("runtime", {}) or {})
        runtime.update({"mode": value, "updated_at": utc_now()})
        state["runtime"] = runtime
        self.store.save(state)
        return value

    def set_halo(self, state_name: object, message: object = "") -> dict[str, str]:
        value = str(state_name or "idle").strip().lower()
        if value not in self.HALO_STATES:
            value = "idle"
        state = self._load()
        runtime = dict(state.get("runtime", {}) or {})
        next_message = self._clean_message(message) or str(runtime.get("message", ""))
        if runtime.get("halo_state") == value and runtime.get("message") == next_message:
            return {"state": value, "message": next_message}
        runtime.update({"halo_state": value, "message": next_message, "updated_at": utc_now()})
        state["runtime"] = runtime
        self.store.save(state)
        return {"state": value, "message": next_message}

    def run_usability_audit(
        self,
        *,
        width: int,
        height: int,
        animation_running: bool,
        owner_switch_available: bool,
        command_input_available: bool,
    ) -> dict[str, Any]:
        status = self.status()
        safety = BusinessConfigStore(self.project_root).ensure()["safety"]
        gates = [
            self._gate("CLIENT_SHELL", width >= 960 and height >= 640),
            self._gate("FIRST_RUN_COMPLETE", status["profile"]["setup_completed"]),
            self._gate("HALO_STATES", len(self.HALO_STATES) == 7),
            self._gate("ANIMATION_RUNNING", animation_running),
            self._gate("OWNER_SWITCH", owner_switch_available),
            self._gate("COMMAND_INPUT", command_input_available),
            self._gate("BUSINESS_BETA_READY", status["business_beta_ready"]),
            self._gate(
                "SAFE_DEFAULTS",
                safety.get("auto_approve") is False
                and safety.get("require_confirmation") is True
                and int(safety.get("max_active_executions", 0)) == 1
                and safety.get("allow_remote_code_execution") is False,
            ),
        ]
        passed = sum(int(item["passed"]) for item in gates)
        audit = {
            "audit_id": uuid4().hex[:16],
            "created_at": utc_now(),
            "status": "PASSED" if passed == len(gates) else "BLOCKED",
            "passed": passed,
            "total": len(gates),
            "window": {"width": int(width), "height": int(height)},
            "gates": gates,
        }
        state = self._load()
        state["usability_audits"] = (
            list(state.get("usability_audits", []) or []) + [audit]
        )[-30:]
        self.store.save(state)
        return audit

    def confirm_stable(self) -> dict[str, Any]:
        state = self._load()
        audits = list(state.get("usability_audits", []) or [])
        if not audits or audits[-1].get("status") != "PASSED":
            raise ValueError("B120: audyt użyteczności nie jest jeszcze zaliczony.")
        if not self._beta_ready():
            raise ValueError("B120: Business Beta B115 nie jest potwierdzona.")
        confirmation = {
            "confirmation_id": uuid4().hex[:16],
            "audit_id": audits[-1]["audit_id"],
            "status": "BUSINESS_1_1_STABLE_READY",
            "confirmed_at": utc_now(),
            "automatic_publication": False,
            "owner_mode_preserved": True,
        }
        state["stable_confirmations"] = (
            list(state.get("stable_confirmations", []) or []) + [confirmation]
        )[-20:]
        self.store.save(state)
        self._export(audits[-1], confirmation)
        return confirmation

    def status(self) -> dict[str, Any]:
        state = self._load()
        profile = dict(state.get("profile", {}) or {})
        runtime = dict(state.get("runtime", {}) or {})
        audits = list(state.get("usability_audits", []) or [])
        confirmations = list(state.get("stable_confirmations", []) or [])
        latest_audit = dict(audits[-1]) if audits else {}
        latest_confirmation = dict(confirmations[-1]) if confirmations else {}
        return {
            "status": "CLIENT_EXPERIENCE_SUITE_READY",
            "stages": dict(self.STAGES),
            "profile": {
                "display_name": str(profile.get("display_name", "Kacper")),
                "voice_enabled": bool(profile.get("voice_enabled", True)),
                "interaction_mode": str(profile.get("interaction_mode", "VOICE_AND_TEXT")),
                "setup_completed": bool(profile.get("setup_completed", False)),
            },
            "runtime": {
                "mode": str(runtime.get("mode", "OWNER")),
                "halo_state": str(runtime.get("halo_state", "idle")),
                "message": str(runtime.get("message", "")),
            },
            "business_beta_ready": self._beta_ready(),
            "latest_audit_status": str(latest_audit.get("status", "NOT_RUN")),
            "gates_passed": int(latest_audit.get("passed", 0) or 0),
            "gates_total": int(latest_audit.get("total", 8) or 8),
            "stable_ready": latest_confirmation.get("status") == "BUSINESS_1_1_STABLE_READY",
            "automatic_publication": False,
            "owner_mode_preserved": True,
        }

    def should_start_client(self) -> bool:
        status = self.status()
        return (
            status["profile"]["setup_completed"]
            and status["runtime"]["mode"] == "CLIENT"
        )

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

    def _beta_ready(self) -> bool:
        try:
            return bool(BusinessBetaReadinessCenter(self.project_root).status()["beta_ready"])
        except Exception:
            return False

    def _export(self, audit: dict[str, Any], confirmation: dict[str, Any]) -> None:
        reports = self.project_root / "AI_PLIKI" / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        payload = {"audit": audit, "confirmation": confirmation, "status": self.status()}
        (reports / "JARVIS_BUSINESS_1_1_STABLE.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        lines = [
            "JARVIS OS 1.1 STABLE",
            f"Status: {confirmation['status']}",
            f"Audyt użyteczności: {audit['passed']}/{audit['total']}",
            "Tryb właściciela zachowany: TAK",
            "Automatyczna publikacja: NIE",
        ]
        (reports / "JARVIS_BUSINESS_1_1_STABLE.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _gate(name: str, passed: bool) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed)}

    @staticmethod
    def _clean_name(value: object) -> str:
        text = " ".join(str(value or "Kacper").split())[:50]
        return re.sub(r"[^\w .ąćęłńóśźżĄĆĘŁŃÓŚŹŻ-]", "", text) or "Użytkownik"

    @staticmethod
    def _clean_message(value: object) -> str:
        return " ".join(str(value or "").split())[:240]

    @staticmethod
    def _interaction_mode(value: object) -> str:
        mode = str(value or "VOICE_AND_TEXT").strip().upper()
        return mode if mode in {"VOICE_AND_TEXT", "TEXT_ONLY"} else "VOICE_AND_TEXT"
