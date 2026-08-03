from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


class MemoryExecutionStore:
    def __init__(self, records=None):
        self.records = [dict(item) for item in (records or [])]

    def list_records(self, *, limit=10000):
        return [dict(item) for item in self.records[:limit]]

    def summary(self):
        counts = {}
        for item in self.records:
            status = str(item.get("status", "UNKNOWN")).upper()
            counts[status] = counts.get(status, 0) + 1
        active_states = {
            "DISPATCHED", "QUEUED", "SCHEDULED", "WAITING_RESOURCES",
            "WAITING_APPROVAL", "RECOVERING", "RUNNING", "PAUSED",
        }
        return {
            "total": len(self.records),
            "active": sum(counts.get(item, 0) for item in active_states),
            "completed": counts.get("COMPLETED", 0),
            "failed": counts.get("FAILED", 0),
            "deferred": counts.get("DEFERRED_CONSTRAINTS", 0),
            "waiting_approval": counts.get("WAITING_APPROVAL", 0),
            "counts": counts,
        }


class MemoryEvolutionStore:
    def __init__(self):
        self.revisions = {
            "r0": {"revision_id": "r0", "status": "SUPERSEDED", "policy": {"x": 0}},
            "r1": {"revision_id": "r1", "status": "ACTIVE", "policy": {"x": 1}},
        }
        self.runtime_value = {"active_revision_id": "r1"}

    def active_revision(self):
        return dict(self.revisions["r1"])

    def previous_active_revision(self):
        return dict(self.revisions["r0"])

    def runtime(self):
        return dict(self.runtime_value)


class FakeEvolution:
    def __init__(self, execution_store=None):
        self.store = MemoryEvolutionStore()
        self.strategic_execution = SimpleNamespace(
            store=execution_store or MemoryExecutionStore()
        )
        self.strategic_portfolio = SimpleNamespace(store=MagicMock())
        self.rollback = MagicMock(return_value={
            "success": True,
            "status": "STRATEGIC_POLICY_EVOLUTION_ROLLED_BACK",
        })


class FakeValidationStore:
    def __init__(self, experiments=None):
        self.values = [dict(item) for item in (experiments or [])]

    def list_experiments(self, *, limit=1000):
        return [dict(item) for item in self.values[:limit]]


class FakeValidation:
    def __init__(self, experiments=None, execution_store=None):
        self.store = FakeValidationStore(experiments)
        self.strategic_policy_evolution = FakeEvolution(execution_store)
        self.strategic_execution = self.strategic_policy_evolution.strategic_execution
        self.strategic_portfolio = self.strategic_policy_evolution.strategic_portfolio
