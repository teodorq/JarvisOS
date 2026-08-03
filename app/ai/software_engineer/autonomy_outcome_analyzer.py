from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any


class AutonomyOutcomeAnalyzer:
    """Builds safe metrics, calibration and lessons from learning episodes."""

    def analyze(
        self,
        episodes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        values = [
            dict(item)
            for item in episodes
            if isinstance(item, dict)
        ]
        total = len(values)
        successful = sum(
            1
            for item in values
            if item.get("success") is True
        )
        failed = total - successful
        rolled_back = sum(
            1
            for item in values
            if item.get("rolled_back") is True
        )
        retries = sum(
            self._integer(item.get("retry_count"))
            for item in values
        )
        failures = sum(
            self._integer(item.get("failure_count"))
            for item in values
        )
        durations = [
            self._number(item.get("duration_seconds"))
            for item in values
            if self._number(item.get("duration_seconds")) > 0
        ]
        estimated_minutes = [
            self._number(item.get("estimated_minutes"))
            for item in values
            if self._number(item.get("estimated_minutes")) > 0
        ]
        actual_minutes = [
            self._number(item.get("actual_minutes"))
            for item in values
            if self._number(item.get("actual_minutes")) > 0
        ]
        statuses = Counter(
            str(item.get("status", "UNKNOWN")).upper()
            for item in values
        )
        types = Counter(
            str(item.get("episode_type", "unknown"))
            for item in values
        )
        subsystem_stats = self._group_stats(
            values,
            key="subsystems",
        )
        signature_stats = self._signature_stats(values)
        calibration = self._calibration(values)
        recommendations = self._recommendations(
            total=total,
            success_rate=self._rate(successful, total),
            rollback_rate=self._rate(rolled_back, total),
            retries=retries,
            calibration=calibration,
            subsystem_stats=subsystem_stats,
        )
        lessons = self._lessons(
            values,
            subsystem_stats=subsystem_stats,
            calibration=calibration,
        )

        return {
            "success": True,
            "status": "AUTONOMY_OUTCOMES_ANALYZED",
            "observations": total,
            "successful": successful,
            "failed": failed,
            "rolled_back": rolled_back,
            "retry_count": retries,
            "failure_count": failures,
            "success_rate": self._rate(successful, total),
            "failure_rate": self._rate(failed, total),
            "rollback_rate": self._rate(rolled_back, total),
            "retry_rate": self._rate(
                sum(
                    1
                    for item in values
                    if self._integer(item.get("retry_count")) > 0
                ),
                total,
            ),
            "average_duration_seconds": round(
                mean(durations) if durations else 0.0,
                3,
            ),
            "average_estimated_minutes": round(
                mean(estimated_minutes) if estimated_minutes else 0.0,
                3,
            ),
            "average_actual_minutes": round(
                mean(actual_minutes) if actual_minutes else 0.0,
                3,
            ),
            "by_status": dict(statuses),
            "by_episode_type": dict(types),
            "subsystems": subsystem_stats,
            "signatures": signature_stats,
            "calibration": calibration,
            "lessons": lessons,
            "recommendations": recommendations,
        }

    def _group_stats(
        self,
        episodes: list[dict[str, Any]],
        *,
        key: str,
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in episodes:
            raw = item.get(key, [])
            if isinstance(raw, (str, bytes)):
                raw = [raw]
            if not isinstance(raw, (list, tuple, set)):
                continue
            for value in raw:
                name = str(value).strip()
                if name:
                    groups[name].append(item)

        result: dict[str, dict[str, Any]] = {}
        for name, values in groups.items():
            total = len(values)
            successful = sum(
                1
                for item in values
                if item.get("success") is True
            )
            rolled_back = sum(
                1
                for item in values
                if item.get("rolled_back") is True
            )
            retries = sum(
                self._integer(item.get("retry_count"))
                for item in values
            )
            result[name] = {
                "observations": total,
                "success_rate": self._rate(successful, total),
                "rollback_rate": self._rate(rolled_back, total),
                "retry_count": retries,
                "risk_bias": round(
                    mean(
                        self._number(item.get("estimated_risk"))
                        for item in values
                    )
                    if values
                    else 0.0,
                    3,
                ),
            }

        return dict(
            sorted(
                result.items(),
                key=lambda pair: (
                    -int(pair[1]["observations"]),
                    pair[0],
                ),
            )
        )

    def _signature_stats(
        self,
        episodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in episodes:
            signature = str(item.get("signature", "")).strip()
            if signature:
                groups[signature].append(item)

        result: dict[str, dict[str, Any]] = {}
        for signature, values in groups.items():
            total = len(values)
            successful = sum(
                1
                for item in values
                if item.get("success") is True
            )
            result[signature] = {
                "observations": total,
                "success_rate": self._rate(successful, total),
                "rollbacks": sum(
                    1
                    for item in values
                    if item.get("rolled_back") is True
                ),
                "retries": sum(
                    self._integer(item.get("retry_count"))
                    for item in values
                ),
                "last_status": str(
                    values[-1].get("status", "UNKNOWN")
                ),
            }

        return result

    def _calibration(
        self,
        episodes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not episodes:
            return {
                "risk_error": 0.0,
                "roi_error": 0.0,
                "time_error_ratio": 0.0,
                "risk_underestimation": 0.0,
                "roi_overestimation": 0.0,
                "samples": 0,
            }

        risk_errors: list[float] = []
        roi_errors: list[float] = []
        time_errors: list[float] = []
        risk_underestimation: list[float] = []
        roi_overestimation: list[float] = []

        for item in episodes:
            predicted_risk = self._scale_10(
                item.get("estimated_risk")
            )
            predicted_roi = self._scale_10(
                item.get("estimated_roi")
            )
            actual_failure = 10.0 if not bool(
                item.get("success", False)
            ) else 0.0
            actual_value = 10.0 if bool(
                item.get("success", False)
            ) and not bool(item.get("rolled_back", False)) else 0.0

            risk_errors.append(abs(predicted_risk - actual_failure))
            roi_errors.append(abs(predicted_roi - actual_value))
            risk_underestimation.append(
                max(0.0, actual_failure - predicted_risk)
            )
            roi_overestimation.append(
                max(0.0, predicted_roi - actual_value)
            )

            estimated = self._number(
                item.get("estimated_minutes")
            )
            actual = self._number(
                item.get("actual_minutes")
            )
            if estimated > 0 and actual > 0:
                time_errors.append(abs(actual - estimated) / estimated)

        return {
            "risk_error": round(mean(risk_errors), 4),
            "roi_error": round(mean(roi_errors), 4),
            "time_error_ratio": round(
                mean(time_errors) if time_errors else 0.0,
                4,
            ),
            "risk_underestimation": round(
                mean(risk_underestimation),
                4,
            ),
            "roi_overestimation": round(
                mean(roi_overestimation),
                4,
            ),
            "samples": len(episodes),
        }

    def _recommendations(
        self,
        *,
        total: int,
        success_rate: float,
        rollback_rate: float,
        retries: int,
        calibration: dict[str, Any],
        subsystem_stats: dict[str, dict[str, Any]],
    ) -> list[str]:
        recommendations: list[str] = []

        if total == 0:
            return [
                "Brak danych. Zachowaj tryb dry-run i automatyczny rollback."
            ]

        if total < 5:
            recommendations.append(
                "Zbierz co najmniej 5 zakończonych przebiegów przed aktywacją profilu."
            )

        if success_rate < 0.75:
            recommendations.append(
                "Zwiększ wagę ryzyka i historii w wyborze kampanii."
            )

        if rollback_rate > 0.15:
            recommendations.append(
                "Utrzymaj rollback_on_stop i obniż maksymalne ryzyko."
            )

        if retries > max(1, total // 3):
            recommendations.append(
                "Ogranicz retry dla powtarzalnych błędów nieretrywalnych."
            )

        if self._number(calibration.get("risk_underestimation")) > 2.0:
            recommendations.append(
                "Podnieś konserwatywnie przewidywane ryzyko przyszłych kampanii."
            )

        if self._number(calibration.get("roi_overestimation")) > 2.0:
            recommendations.append(
                "Obniż wpływ deklarowanego ROI bez potwierdzenia historycznego."
            )

        weakest = [
            name
            for name, metrics in subsystem_stats.items()
            if int(metrics.get("observations", 0)) >= 2
            and self._number(metrics.get("success_rate")) < 0.6
        ]
        if weakest:
            recommendations.append(
                "Wymagaj dodatkowej walidacji dla podsystemów: "
                + ", ".join(weakest[:5])
            )

        if not recommendations:
            recommendations.append(
                "Historia jest stabilna. Zachowaj bezpieczne ustawienia i kontynuuj naukę."
            )

        return recommendations

    def _lessons(
        self,
        episodes: list[dict[str, Any]],
        *,
        subsystem_stats: dict[str, dict[str, Any]],
        calibration: dict[str, Any],
    ) -> list[dict[str, Any]]:
        lessons: list[dict[str, Any]] = []

        for subsystem, metrics in subsystem_stats.items():
            observations = int(metrics.get("observations", 0))
            if observations < 2:
                continue
            success_rate = self._number(metrics.get("success_rate"))
            if success_rate >= 0.8:
                lessons.append(
                    {
                        "kind": "subsystem_strength",
                        "scope": subsystem,
                        "confidence": round(
                            min(1.0, observations / 10.0),
                            3,
                        ),
                        "message": (
                            f"Podsystem {subsystem} ma stabilną historię "
                            f"sukcesu ({success_rate:.0%})."
                        ),
                    }
                )
            elif success_rate < 0.6:
                lessons.append(
                    {
                        "kind": "subsystem_risk",
                        "scope": subsystem,
                        "confidence": round(
                            min(1.0, observations / 10.0),
                            3,
                        ),
                        "message": (
                            f"Podsystem {subsystem} wymaga ostrożniejszej "
                            f"walidacji ({success_rate:.0%} sukcesów)."
                        ),
                    }
                )

        if self._number(calibration.get("risk_underestimation")) > 1.5:
            lessons.append(
                {
                    "kind": "risk_calibration",
                    "scope": "global",
                    "confidence": round(
                        min(
                            1.0,
                            int(calibration.get("samples", 0)) / 20.0,
                        ),
                        3,
                    ),
                    "message": (
                        "Historyczne ryzyko było niedoszacowane; "
                        "należy zwiększyć wagę ryzyka."
                    ),
                }
            )

        if self._number(calibration.get("roi_overestimation")) > 1.5:
            lessons.append(
                {
                    "kind": "roi_calibration",
                    "scope": "global",
                    "confidence": round(
                        min(
                            1.0,
                            int(calibration.get("samples", 0)) / 20.0,
                        ),
                        3,
                    ),
                    "message": (
                        "Deklarowane ROI było zawyżone; "
                        "należy silniej uwzględniać historię."
                    ),
                }
            )

        error_counter: Counter[str] = Counter()
        for item in episodes:
            for error in item.get("errors", []):
                text = str(error).strip()
                if text:
                    error_counter[text[:200]] += 1

        for error, count in error_counter.most_common(5):
            if count < 2:
                continue
            lessons.append(
                {
                    "kind": "recurring_error",
                    "scope": "global",
                    "confidence": round(
                        min(1.0, count / 5.0),
                        3,
                    ),
                    "message": (
                        f"Powtarzalny błąd ({count}x): {error}"
                    ),
                }
            )

        return lessons[:30]

    @staticmethod
    def _rate(value: int, total: int) -> float:
        return round(value / total, 4) if total else 0.0

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _scale_10(cls, value: Any) -> float:
        return max(
            0.0,
            min(
                10.0,
                cls._number(value),
            ),
        )

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
