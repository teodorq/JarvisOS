from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any
import uuid

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


class DailyWorkService:
    """B100 persistent multi-step work, reminders and local reports."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.root / "data" / "assistant" / "daily_work.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "active_workflow_id": "",
            "workflows": {},
            "reminders": [],
            "reports": [],
            "updated_at": "",
        }

    def create_workflow(self, title: str, steps: list[str]) -> dict[str, Any]:
        clean_title = " ".join(str(title).split()).strip()
        clean_steps = [" ".join(str(step).split()).strip()[:300] for step in steps]
        clean_steps = [step for step in clean_steps if step]
        if not clean_title:
            raise ValueError("Nazwa zadania nie może być pusta.")
        if not clean_steps:
            raise ValueError("Zadanie musi mieć co najmniej jeden krok.")
        if len(clean_steps) > 30:
            raise ValueError("Zadanie może mieć maksymalnie 30 kroków.")
        data = self._load()
        workflow_id = uuid.uuid4().hex
        now = utc_now()
        workflow = {
            "workflow_id": workflow_id,
            "title": clean_title[:160],
            "status": "READY",
            "current_step": 0,
            "steps": [
                {
                    "index": index,
                    "command": step,
                    "status": "PENDING",
                    "completed_at": "",
                }
                for index, step in enumerate(clean_steps)
            ],
            "created_at": now,
            "updated_at": now,
        }
        workflows = dict(data.get("workflows", {}) or {})
        workflows[workflow_id] = workflow
        data["workflows"] = workflows
        data["active_workflow_id"] = workflow_id
        data["updated_at"] = now
        self.store.save(data)
        return workflow

    def start(self, query: str = "") -> dict[str, Any]:
        data = self._load()
        workflow_id = self._find_workflow_id(data, query) or str(data.get("active_workflow_id", ""))
        workflow = self._require_workflow(data, workflow_id)
        if workflow["status"] == "COMPLETED":
            raise ValueError("To zadanie jest już ukończone.")
        workflow["status"] = "RUNNING"
        workflow["updated_at"] = utc_now()
        self._save_workflow(data, workflow)
        return workflow

    def complete_current_step(self) -> dict[str, Any]:
        data = self._load()
        workflow = self._active(data)
        if workflow["status"] not in {"RUNNING", "READY"}:
            raise ValueError("Aktywne zadanie nie jest gotowe do wykonania kroku.")
        steps = list(workflow.get("steps", []) or [])
        index = int(workflow.get("current_step", 0))
        if index >= len(steps):
            workflow["status"] = "COMPLETED"
            self._save_workflow(data, workflow)
            return workflow
        step = dict(steps[index])
        step["status"] = "COMPLETED"
        step["completed_at"] = utc_now()
        steps[index] = step
        workflow["steps"] = steps
        workflow["current_step"] = index + 1
        workflow["status"] = "COMPLETED" if index + 1 >= len(steps) else "RUNNING"
        workflow["updated_at"] = utc_now()
        self._save_workflow(data, workflow)
        return workflow

    def pause(self) -> dict[str, Any]:
        return self._set_active_status("PAUSED")

    def resume(self) -> dict[str, Any]:
        return self._set_active_status("RUNNING")

    def cancel(self) -> dict[str, Any]:
        return self._set_active_status("CANCELLED")

    def add_reminder(self, text: str, *, minutes: int = 0) -> dict[str, Any]:
        clean_text = " ".join(str(text).split()).strip()
        if not clean_text:
            raise ValueError("Treść przypomnienia nie może być pusta.")
        safe_minutes = max(0, min(int(minutes), 525600))
        due_at = datetime.now(timezone.utc) + timedelta(minutes=safe_minutes)
        reminder = {
            "reminder_id": uuid.uuid4().hex,
            "text": clean_text[:300],
            "due_at": due_at.isoformat(),
            "status": "PENDING",
            "created_at": utc_now(),
        }
        data = self._load()
        reminders = list(data.get("reminders", []) or [])
        reminders.append(reminder)
        data["reminders"] = reminders[-500:]
        data["updated_at"] = utc_now()
        self.store.save(data)
        return reminder

    def due_reminders(self, *, mark_delivered: bool = False) -> list[dict[str, Any]]:
        data = self._load()
        now = datetime.now(timezone.utc)
        reminders = list(data.get("reminders", []) or [])
        due: list[dict[str, Any]] = []
        for index, item in enumerate(reminders):
            reminder = dict(item)
            due_at = parse_iso(reminder.get("due_at"))
            if reminder.get("status") == "PENDING" and due_at and due_at <= now:
                due.append(reminder)
                if mark_delivered:
                    reminder["status"] = "DELIVERED"
                    reminder["delivered_at"] = utc_now()
                    reminders[index] = reminder
        if mark_delivered and due:
            data["reminders"] = reminders
            data["updated_at"] = utc_now()
            self.store.save(data)
        return due

    def export_report(self) -> dict[str, Any]:
        status = self.status()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = self.root / "AI_PLIKI" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"JARVIS_DAILY_WORK_{timestamp}.txt"
        active = dict(status.get("active_workflow", {}) or {})
        lines = [
            "JARVIS OS — RAPORT CODZIENNEJ PRACY",
            f"Utworzono: {utc_now()}",
            f"Workflow: {status['workflow_count']}",
            f"Przypomnienia oczekujące: {status['pending_reminders']}",
            f"Przypomnienia wymagające uwagi: {status['due_reminders']}",
            f"Aktywne zadanie: {active.get('title', 'BRAK')}",
            f"Postęp: {active.get('completed_steps', 0)}/{active.get('total_steps', 0)}",
            f"Status: {active.get('status', 'BRAK')}",
        ]
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        data = self._load()
        reports = list(data.get("reports", []) or [])
        reports.append({"path": str(report_path), "created_at": utc_now()})
        data["reports"] = reports[-100:]
        data["updated_at"] = utc_now()
        self.store.save(data)
        return {"status": "DAILY_WORK_REPORT_EXPORTED", "path": str(report_path)}

    def status(self) -> dict[str, Any]:
        data = self._load()
        workflows = dict(data.get("workflows", {}) or {})
        active_id = str(data.get("active_workflow_id", ""))
        active = dict(workflows.get(active_id, {}) or {})
        steps = list(active.get("steps", []) or [])
        current_index = int(active.get("current_step", 0) or 0)
        active_summary = {
            "workflow_id": active.get("workflow_id", ""),
            "title": active.get("title", ""),
            "status": active.get("status", "IDLE"),
            "completed_steps": sum(1 for step in steps if step.get("status") == "COMPLETED"),
            "total_steps": len(steps),
            "next_step": (
                str(steps[current_index].get("command", ""))
                if current_index < len(steps)
                else ""
            ),
        }
        pending = [item for item in data.get("reminders", []) if item.get("status") == "PENDING"]
        return {
            "status": "DAILY_WORK_CENTER_READY",
            "workflow_count": len(workflows),
            "active_workflow": active_summary,
            "pending_reminders": len(pending),
            "due_reminders": len(self.due_reminders()),
            "report_count": len(list(data.get("reports", []) or [])),
        }

    @staticmethod
    def parse_workflow_command(command: str) -> tuple[str, list[str]]:
        text = str(command).strip()
        match = re.search(
            r"(?:utwórz|utworz)\s+zadanie\s+wieloetapowe\s+(.+?)(?::|\s+kroki?:)\s*(.+)$",
            text,
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("Użyj: Utwórz zadanie wieloetapowe NAZWA: krok 1; krok 2.")
        title = match.group(1).strip()
        steps = [part.strip() for part in re.split(r"[;|]", match.group(2)) if part.strip()]
        return title, steps

    @staticmethod
    def parse_reminder_command(command: str) -> tuple[str, int]:
        text = str(command).strip()
        minutes_match = re.search(r"\bza\s+(\d+)\s+min", text, re.IGNORECASE)
        minutes = int(minutes_match.group(1)) if minutes_match else 0
        content = re.sub(r"^(?:dodaj przypomnienie|przypomnij mi)\s*", "", text, flags=re.IGNORECASE)
        content = re.sub(r"\s+za\s+\d+\s+min(?:ut(?:y|ę)?)?\s*$", "", content, flags=re.IGNORECASE)
        return content.strip(" .,:;"), minutes

    def _set_active_status(self, status: str) -> dict[str, Any]:
        data = self._load()
        workflow = self._active(data)
        workflow["status"] = status
        workflow["updated_at"] = utc_now()
        self._save_workflow(data, workflow)
        return workflow

    def _save_workflow(self, data: dict[str, Any], workflow: dict[str, Any]) -> None:
        workflows = dict(data.get("workflows", {}) or {})
        workflows[str(workflow["workflow_id"])] = workflow
        data["workflows"] = workflows
        data["active_workflow_id"] = str(workflow["workflow_id"])
        data["updated_at"] = utc_now()
        self.store.save(data)

    def _active(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._require_workflow(data, str(data.get("active_workflow_id", "")))

    @staticmethod
    def _require_workflow(data: dict[str, Any], workflow_id: str) -> dict[str, Any]:
        workflow = dict(dict(data.get("workflows", {}) or {}).get(workflow_id, {}) or {})
        if not workflow:
            raise KeyError("Brak aktywnego zadania wieloetapowego.")
        return workflow

    @staticmethod
    def _find_workflow_id(data: dict[str, Any], query: str) -> str:
        folded = str(query).casefold().strip()
        if not folded:
            return ""
        for workflow_id, workflow in dict(data.get("workflows", {}) or {}).items():
            if folded in {workflow_id.casefold(), str(workflow.get("title", "")).casefold()}:
                return workflow_id
        return ""

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
