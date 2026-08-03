from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import count_statuses, now


_PATTERNS = (
    ("SHELL_TRUE", re.compile(r"shell\s*=\s*True")),
    ("DYNAMIC_EVAL", re.compile(r"\beval\s*\(")),
    ("DYNAMIC_EXEC", re.compile(r"\bexec\s*\(")),
    ("HARDCODED_SECRET", re.compile(
        r"(?i)(api[_-]?key|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"
    )),
)
_ALLOWED_SUFFIXES = {".py", ".ps1", ".cmd", ".bat", ".json", ".txt"}


class SecurityHardeningService:
    """B78 bounded static security audit and policy hardening."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store

    def audit(self) -> dict[str, Any]:
        policy = self.store.policy("B78")
        max_files = int(policy.get("max_scan_files", 5000))
        max_findings = int(policy.get("max_findings", 500))
        findings: list[dict[str, Any]] = []
        scanned = 0
        for path in self.project_root.rglob("*"):
            if scanned >= max_files or len(findings) >= max_findings:
                break
            if not path.is_file() or path.suffix.casefold() not in _ALLOWED_SUFFIXES:
                continue
            if any(part in {"archive", ".git", ".venv", "venv", "__pycache__"} for part in path.parts):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            relative = str(path.relative_to(self.project_root)).replace("\\", "/")
            for category, pattern in _PATTERNS:
                for match in pattern.finditer(text):
                    findings.append({
                        "audit_id": f"security-finding-{uuid4().hex}",
                        "status": "OPEN",
                        "severity": "HIGH" if category == "HARDCODED_SECRET" else "MEDIUM",
                        "category": category,
                        "path": relative,
                        "line": text.count("\n", 0, match.start()) + 1,
                        "summary": f"Wykryto wzorzec {category}.",
                        "created_at": now(),
                    })
                    if len(findings) >= max_findings:
                        break
                if len(findings) >= max_findings:
                    break

        policy_findings = self._policy_findings()
        findings.extend(policy_findings[:max(0, max_findings - len(findings))])
        self.store.replace_records("B78", findings)
        runtime = self.store.runtime("B78")
        self.store.update_runtime("B78", {
            "enabled": True,
            "phase": "READY" if not findings else "FINDINGS",
            "cycles_completed": int(runtime.get("cycles_completed", 0) or 0) + 1,
            "last_cycle_at": now(),
            "last_status": "SECURITY_HARDENING_AUDIT_COMPLETED",
            "last_decision": "CLEAR" if not findings else "REVIEW",
            "last_record_id": str(findings[-1].get("audit_id", "")) if findings else "",
            "last_result": {"scanned": scanned, "findings": len(findings)},
            "last_error": "",
        })
        self.store.record_history("B78", {
            "status": "SECURITY_HARDENING_AUDIT_COMPLETED",
            "success": True,
            "phase": "READY" if not findings else "FINDINGS",
            "decision": "CLEAR" if not findings else "REVIEW",
            "reason": f"Przeskanowano {scanned}, znaleziska {len(findings)}",
            "error": "",
        })
        return self._response(
            "SECURITY_HARDENING_AUDIT_COMPLETED",
            success=True,
            decision="CLEAR" if not findings else "REVIEW",
            scanned_files=scanned,
            findings=findings,
            finding_counts=count_statuses(findings),
        )

    def apply_safe_hardening(self) -> dict[str, Any]:
        changed = []
        for stage in sorted(self.store.load().get("policy", {})):
            before = self.store.policy(stage)
            updates = {"auto_approve": False}
            if stage == "B64":
                updates["max_active_leases"] = 1
            after = self.store.update_policy(stage, updates)
            if before != after:
                changed.append(stage)
        record = self.store.append_record("B78", {
            "audit_id": f"security-hardening-{uuid4().hex}",
            "status": "RESOLVED",
            "severity": "INFO",
            "category": "SAFE_POLICY_HARDENING",
            "path": str(self.store.path),
            "summary": (
                "Wymuszono auto_approve=False i maksymalnie jedną "
                "dzierżawę B64."
            ),
            "changed_stages": changed,
            "created_at": now(),
        })
        return self._response(
            "SECURITY_HARDENING_APPLIED",
            success=True,
            decision="HARDEN",
            finding=record,
            changed_stages=changed,
        )

    def status(self) -> dict[str, Any]:
        findings = self.store.list_records("B78", limit=100)
        return self._response(
            "SECURITY_HARDENING_STATUS",
            success=True,
            findings=findings,
            finding_counts=count_statuses(findings),
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "SECURITY_HARDENING_HISTORY",
            success=True,
            findings=self.store.list_records("B78", limit=limit),
            history=self.store.history(stage="B78", limit=limit),
        )

    def _policy_findings(self) -> list[dict[str, Any]]:
        result = []
        payload = self.store.load()
        for stage, policy in payload.get("policy", {}).items():
            if bool(dict(policy).get("auto_approve", False)):
                result.append({
                    "audit_id": f"security-policy-{uuid4().hex}",
                    "status": "OPEN",
                    "severity": "CRITICAL",
                    "category": "AUTO_APPROVE_ENABLED",
                    "path": str(self.store.path),
                    "summary": f"{stage} ma auto_approve=True.",
                    "created_at": now(),
                })
        if int(self.store.policy("B64").get("max_active_leases", 1)) > 1:
            result.append({
                "audit_id": f"security-policy-{uuid4().hex}",
                "status": "OPEN",
                "severity": "HIGH",
                "category": "MULTIPLE_ACTIVE_LEASES_ALLOWED",
                "path": str(self.store.path),
                "summary": "B64 dopuszcza więcej niż jedną aktywną dzierżawę.",
                "created_at": now(),
            })
        return result

    def _response(
        self,
        status: str,
        *,
        success: bool,
        errors: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "success": success,
            "status": status,
            "operation": "autonomy_governance_suite",
            "stage": "B78",
            "runtime": self.store.runtime("B78"),
            "policy": self.store.policy("B78"),
            "summary": self.store.summary("B78"),
            "report_path": str(self.store.path),
            "errors": list(errors or []),
            **extra,
        }
