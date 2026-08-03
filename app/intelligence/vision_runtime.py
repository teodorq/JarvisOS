from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9ąćęłńóśźż]+", str(value).casefold())
        if len(token) > 1
    }


class VisionRuntimeV3:
    """B101 persistent visual observations with stable element identity."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "intelligence" / "vision3.json",
            self._default,
        )
        if not self.store.exists():
            self.store.save(self._default())

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "3.0",
            "observations": [],
            "verifications": {},
            "last_selection": {},
            "updated_at": "",
        }

    def observe(
        self,
        window_title: object,
        elements: Iterable[dict[str, Any]] | None = None,
        *,
        source: str = "runtime",
    ) -> dict[str, Any]:
        title = " ".join(str(window_title).split()).strip() or "Nieznane okno"
        normalized = [self._normalize_element(title, item) for item in (elements or [])]
        data = self._load()
        previous = self.latest()
        observation = {
            "observation_id": self._id(f"{title}|{utc_now()}"),
            "window_title": title,
            "source": str(source)[:80],
            "elements": normalized[:500],
            "created_at": utc_now(),
        }
        observation["changes"] = self.compare(previous, observation)
        observations = list(data.get("observations", []) or [])
        observations.append(observation)
        data["observations"] = observations[-80:]
        data["updated_at"] = utc_now()
        self.store.save(data)
        return observation

    def latest(self) -> dict[str, Any]:
        observations = list(self._load().get("observations", []) or [])
        return dict(observations[-1]) if observations else {}

    def select(self, query: object, *, min_confidence: float = 0.35) -> dict[str, Any]:
        observation = self.latest()
        query_tokens = _tokens(query)
        best: tuple[float, dict[str, Any]] | None = None
        for element in observation.get("elements", []) or []:
            candidate = dict(element)
            candidate_tokens = _tokens(
                f"{candidate.get('label', '')} {candidate.get('role', '')} "
                f"{candidate.get('text', '')}"
            )
            overlap = len(query_tokens & candidate_tokens)
            union = max(1, len(query_tokens | candidate_tokens))
            lexical = overlap / union
            confidence = float(candidate.get("confidence", 0.0) or 0.0)
            score = round((lexical * 0.75) + (confidence * 0.25), 4)
            if best is None or score > best[0]:
                best = (score, candidate)
        selected = dict(best[1]) if best and best[0] >= min_confidence else {}
        data = self._load()
        data["last_selection"] = {
            "query": str(query),
            "score": best[0] if best else 0.0,
            "element": selected,
            "created_at": utc_now(),
        }
        data["updated_at"] = utc_now()
        self.store.save(data)
        return selected

    def begin_verification(
        self,
        action_id: str,
        expected: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._load()
        verifications = dict(data.get("verifications", {}) or {})
        record = {
            "action_id": str(action_id),
            "expected": dict(expected or {}),
            "status": "PENDING",
            "created_at": utc_now(),
            "checked_at": "",
        }
        verifications[str(action_id)] = record
        data["verifications"] = verifications
        data["updated_at"] = utc_now()
        self.store.save(data)
        return record

    def verify(
        self,
        action_id: str,
        observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = self._load()
        verifications = dict(data.get("verifications", {}) or {})
        record = dict(verifications.get(str(action_id), {}) or {})
        if not record:
            raise KeyError("Brak oczekującej weryfikacji Vision 3.0.")
        current = dict(observation or self.latest())
        expected = dict(record.get("expected", {}) or {})
        checks = self._checks(expected, current)
        record.update({
            "status": "VERIFIED" if checks and all(checks.values()) else "NOT_VERIFIED",
            "checks": checks,
            "checked_at": utc_now(),
            "observation_id": current.get("observation_id", ""),
        })
        verifications[str(action_id)] = record
        data["verifications"] = verifications
        data["updated_at"] = utc_now()
        self.store.save(data)
        return record

    def status(self) -> dict[str, Any]:
        data = self._load()
        observations = list(data.get("observations", []) or [])
        latest = dict(observations[-1]) if observations else {}
        verifications = list(dict(data.get("verifications", {}) or {}).values())
        return {
            "status": "VISION_3_READY",
            "observation_count": len(observations),
            "window_title": latest.get("window_title", ""),
            "element_count": len(list(latest.get("elements", []) or [])),
            "last_changes": dict(latest.get("changes", {}) or {}),
            "verified_actions": sum(item.get("status") == "VERIFIED" for item in verifications),
            "pending_verifications": sum(item.get("status") == "PENDING" for item in verifications),
            "last_selection": dict(data.get("last_selection", {}) or {}),
        }

    @staticmethod
    def compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        before = {
            str(item.get("element_id")): item
            for item in previous.get("elements", []) or []
            if item.get("element_id")
        }
        after = {
            str(item.get("element_id")): item
            for item in current.get("elements", []) or []
            if item.get("element_id")
        }
        shared = before.keys() & after.keys()
        changed = [
            key for key in shared
            if before[key].get("text") != after[key].get("text")
            or before[key].get("bounds") != after[key].get("bounds")
        ]
        return {
            "window_changed": previous.get("window_title") not in {None, current.get("window_title")},
            "added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "changed": sorted(changed),
        }

    def _normalize_element(self, title: str, item: dict[str, Any]) -> dict[str, Any]:
        value = dict(item or {})
        label = " ".join(str(value.get("label") or value.get("text") or "").split())
        role = " ".join(str(value.get("role") or "element").split()).casefold()
        bounds = value.get("bounds", [])
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
            bounds = []
        identity = f"{title.casefold()}|{role}|{label.casefold()}|{list(bounds)}"
        return {
            "element_id": str(value.get("element_id") or self._id(identity)),
            "label": label[:300],
            "text": str(value.get("text", label))[:500],
            "role": role[:80],
            "bounds": [int(number) for number in bounds] if bounds else [],
            "confidence": max(0.0, min(float(value.get("confidence", 0.75)), 1.0)),
            "enabled": bool(value.get("enabled", True)),
            "visible": bool(value.get("visible", True)),
        }

    @staticmethod
    def _checks(expected: dict[str, Any], observation: dict[str, Any]) -> dict[str, bool]:
        title = str(observation.get("window_title", "")).casefold()
        elements = list(observation.get("elements", []) or [])
        content = " ".join(
            f"{item.get('label', '')} {item.get('text', '')}" for item in elements
        ).casefold()
        checks: dict[str, bool] = {}
        if expected.get("window_contains"):
            checks["window_contains"] = str(expected["window_contains"]).casefold() in title
        if expected.get("element_present"):
            checks["element_present"] = str(expected["element_present"]).casefold() in content
        if expected.get("element_absent"):
            checks["element_absent"] = str(expected["element_absent"]).casefold() not in content
        if expected.get("text_contains"):
            checks["text_contains"] = str(expected["text_contains"]).casefold() in content
        return checks or {"observation_available": bool(observation)}

    @staticmethod
    def _id(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()
