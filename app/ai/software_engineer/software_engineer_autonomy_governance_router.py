from __future__ import annotations

from typing import Any

from .autonomy_governance_suite import bootstrap_autonomy_governance_suite
from .software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)


_OPERATIONS_ROUTER = SoftwareEngineerAutonomyOperationsRouter()


class SoftwareEngineerAutonomyGovernanceRouter:
    """Polish/English GUI routing for the integrated B62-B83 suite."""

    READ_PHRASES = (
        "status wdrażania polityki", "status wdrazania polityki", "status b62",
        "historia wdrożeń polityki", "historia wdrozen polityki",
        "status zarządzania celami", "status zarzadzania celami", "status b63",
        "historia zarządzania celami", "historia zarzadzania celami",
        "status budżetu autonomii", "status budzetu autonomii", "status zasobów autonomii", "status zasobow autonomii", "status b64",
        "status uczenia przyczynowego", "status b65", "historia uczenia przyczynowego",
        "status wydań autonomicznych", "status wydan autonomicznych", "status b66", "historia wydań autonomicznych", "historia wydan autonomicznych",
        "status samokonserwacji", "status konserwacji jarvisa", "status b67", "historia samokonserwacji",
        "status autonomii 24/7", "status autonomii 24x7", "status b68", "historia autonomii 24/7",
        "status b62-b68", "status b62-b69", "status b62-b70",
        "status zarządzania autonomią", "status zarzadzania autonomia",
        "status centrum incydentów", "status centrum incydentow",
        "status incydentów autonomii", "status incydentow autonomii",
        "status b69", "historia incydentów autonomii",
        "historia incydentow autonomii",
        "status odzyskiwania autonomii", "status odzyskiwania jarvisa",
        "status orkiestratora odzyskiwania", "status b70",
        "historia odzyskiwania autonomii",
        "autonomous recovery status", "autonomous recovery history",
        "safe policy deployment status", "goal governance status",
        "resource budget status", "causal learning status",
        "autonomous release status", "self maintenance status",
        "full autonomy 24x7 status", "autonomous incident response status",
    )

    MUTATING_PHRASES = (
        "przeprowadź cykl wdrożenia polityki", "przeprowadz cykl wdrozenia polityki", "wycofaj ostatnią politykę", "wycofaj ostatnia polityke",
        "przeprowadź audyt celów", "przeprowadz audyt celow", "zarządzaj celami autonomicznie", "zarzadzaj celami autonomicznie",
        "odśwież budżet autonomii", "odswiez budzet autonomii", "resetuj obwód błędów autonomii", "resetuj obwod bledow autonomii",
        "przeprowadź analizę przyczynową", "przeprowadz analize przyczynowa",
        "utwórz kandydata wydania", "utworz kandydata wydania", "aktywuj wydanie autonomiczne", "przygotuj rollback wydania", "przywróć poprzednie wydanie", "przywroc poprzednie wydanie",
        "przeskanuj konserwację projektu", "przeskanuj konserwacje projektu", "wykonaj bezpieczne sprzątanie", "wykonaj bezpieczne sprzatanie",
        "uruchom autonomię 24/7", "uruchom autonomie 24/7", "uruchom autonomię 24x7", "zatrzymaj autonomię 24/7", "zatrzymaj autonomie 24/7", "wstrzymaj autonomię 24/7", "wstrzymaj autonomie 24/7", "wznów autonomię 24/7", "wznow autonomie 24/7", "przeprowadź cykl autonomii 24/7", "przeprowadz cykl autonomii 24/7",
        "uruchom monitor incydentów", "uruchom monitor incydentow",
        "uruchom centrum incydentów", "uruchom centrum incydentow",
        "zatrzymaj monitor incydentów", "zatrzymaj monitor incydentow",
        "zatrzymaj centrum incydentów", "zatrzymaj centrum incydentow",
        "wstrzymaj monitor incydentów", "wstrzymaj monitor incydentow",
        "wstrzymaj centrum incydentów", "wstrzymaj centrum incydentow",
        "wznów monitor incydentów", "wznow monitor incydentow",
        "wznów centrum incydentów", "wznow centrum incydentow",
        "przeprowadź skan incydentów", "przeprowadz skan incydentow",
        "ogranicz ostatni incydent", "zamknij ostatni incydent",
        "run safe policy deployment cycle", "run goal governance cycle",
        "refresh resource budget", "run causal learning cycle",
        "create autonomous release candidate", "activate autonomous release",
        "restore previous autonomous release", "scan self maintenance",
        "apply safe maintenance cleanup", "start full autonomy 24x7",
        "stop full autonomy 24x7", "pause full autonomy 24x7",
        "resume full autonomy 24x7", "run full autonomy 24x7 cycle",
        "start autonomous incident monitor", "stop autonomous incident monitor",
        "pause autonomous incident monitor", "resume autonomous incident monitor",
        "run autonomous incident scan", "contain latest autonomous incident",
        "resolve latest autonomous incident",
        "przygotuj plan odzyskiwania", "zbuduj plan odzyskiwania",
        "wykonaj bezpieczne odzyskiwanie", "zweryfikuj odzyskiwanie",
        "przeprowadź cykl odzyskiwania", "przeprowadz cykl odzyskiwania",
        "uruchom odzyskiwanie autonomii", "uruchom autonomiczne odzyskiwanie",
        "uruchom orkiestrator odzyskiwania", "uruchom nadzorcę odzyskiwania",
        "uruchom nadzorce odzyskiwania",
        "zatrzymaj odzyskiwanie autonomii",
        "zatrzymaj orkiestrator odzyskiwania", "zatrzymaj nadzorcę odzyskiwania",
        "zatrzymaj nadzorce odzyskiwania",
        "wstrzymaj odzyskiwanie autonomii",
        "wstrzymaj orkiestrator odzyskiwania",
        "wznów odzyskiwanie autonomii", "wznow odzyskiwanie autonomii",
        "wznów orkiestrator odzyskiwania", "wznow orkiestrator odzyskiwania",
        "prepare autonomous recovery plan", "execute safe autonomous recovery",
        "verify autonomous recovery", "run autonomous recovery cycle",
        "start autonomous recovery supervisor", "stop autonomous recovery supervisor",
        "pause autonomous recovery supervisor", "resume autonomous recovery supervisor",
    )

    @classmethod
    def can_handle(cls, command: str) -> bool:
        normalized = " ".join(str(command).casefold().split())
        return (
            _OPERATIONS_ROUTER.can_handle(normalized)
            or any(
                phrase in normalized
                for phrase in cls.READ_PHRASES + cls.MUTATING_PHRASES
            )
        )

    def try_handle(
        self,
        controller: Any,
        *,
        command: str,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        operation = str(
            context.get("autonomy_governance_action", context.get("operation", ""))
        ).strip().casefold()
        normalized = controller._normalize(command)
        if not (
            self.can_handle(normalized)
            or operation.startswith(("b6", "b7", "b8", "b9"))
            or operation.startswith("autonomy_governance")
        ):
            return None
        validation = getattr(controller, "strategic_policy_validation_service", None)
        if validation is None:
            return {
                "success": False,
                "status": "AUTONOMY_GOVERNANCE_BOOTSTRAP_UNAVAILABLE",
                "operation": "autonomy_governance_suite",
                "stage": "B62-B70",
                "errors": ["Brak usługi B61 wymaganej przez B62-B70."],
            }
        suite = bootstrap_autonomy_governance_suite(
            controller,
            strategic_policy_validation=validation,
        )
        operations_result = _OPERATIONS_ROUTER.try_handle(
            suite,
            command=normalized,
            operation=operation,
        )
        if operations_result is not None:
            return operations_result
        action = self._action(operation, normalized)
        if action == "suite_status":
            return suite.status()
        service, method = self._target(suite, action)
        return getattr(service, method)()

    @classmethod
    def _action(cls, operation: str, normalized: str) -> str:
        checks = (
            ("suite_status", (
                "status b62-b68", "status b62-b69", "status b62-b70",
                "status zarządzania autonomią",
                "status zarzadzania autonomia",
            )),
            ("b62_cycle", ("cykl wdrożenia polityki", "cykl wdrozenia polityki", "run safe policy deployment cycle")),
            ("b62_rollback", ("wycofaj ostatnią politykę", "wycofaj ostatnia polityke")),
            ("b62_history", ("historia wdrożeń polityki", "historia wdrozen polityki")),
            ("b62_status", ("status wdrażania polityki", "status wdrazania polityki", "status b62", "safe policy deployment status")),
            ("b63_cycle", ("audyt celów", "audyt celow", "zarządzaj celami", "zarzadzaj celami", "run goal governance cycle")),
            ("b63_history", ("historia zarządzania celami", "historia zarzadzania celami")),
            ("b63_status", ("status zarządzania celami", "status zarzadzania celami", "status b63", "goal governance status")),
            ("b64_reset", ("resetuj obwód błędów", "resetuj obwod bledow")),
            ("b64_status", ("status budżetu autonomii", "status budzetu autonomii", "status zasobów autonomii", "status zasobow autonomii", "status b64", "resource budget status", "odśwież budżet", "odswiez budzet")),
            ("b65_cycle", ("analizę przyczynową", "analize przyczynowa", "run causal learning cycle")),
            ("b65_history", ("historia uczenia przyczynowego",)),
            ("b65_status", ("status uczenia przyczynowego", "status b65", "causal learning status")),
            ("b66_create", ("utwórz kandydata wydania", "utworz kandydata wydania", "create autonomous release candidate")),
            ("b66_activate", ("aktywuj wydanie autonomiczne", "activate autonomous release")),
            ("b66_prepare_rollback", ("przygotuj rollback wydania",)),
            ("b66_restore", ("przywróć poprzednie wydanie", "przywroc poprzednie wydanie", "restore previous autonomous release")),
            ("b66_history", ("historia wydań autonomicznych", "historia wydan autonomicznych")),
            ("b66_status", ("status wydań autonomicznych", "status wydan autonomicznych", "status b66", "autonomous release status")),
            ("b67_cleanup", ("bezpieczne sprzątanie", "bezpieczne sprzatanie", "apply safe maintenance cleanup")),
            ("b67_scan", ("przeskanuj konserwację", "przeskanuj konserwacje", "scan self maintenance")),
            ("b67_history", ("historia samokonserwacji",)),
            ("b67_status", ("status samokonserwacji", "status konserwacji jarvisa", "status b67", "self maintenance status")),
            ("b68_cycle", ("cykl autonomii 24/7", "run full autonomy 24x7 cycle")),
            ("b68_stop", ("zatrzymaj autonomię 24/7", "zatrzymaj autonomie 24/7", "stop full autonomy 24x7")),
            ("b68_pause", ("wstrzymaj autonomię 24/7", "wstrzymaj autonomie 24/7", "pause full autonomy 24x7")),
            ("b68_resume", ("wznów autonomię 24/7", "wznow autonomie 24/7", "resume full autonomy 24x7")),
            ("b68_start", ("uruchom autonomię 24/7", "uruchom autonomie 24/7", "uruchom autonomię 24x7", "start full autonomy 24x7")),
            ("b68_history", ("historia autonomii 24/7",)),
            ("b68_status", ("status autonomii 24/7", "status autonomii 24x7", "status b68", "full autonomy 24x7 status")),
            ("b69_resolve", ("zamknij ostatni incydent", "resolve latest autonomous incident")),
            ("b69_contain", ("ogranicz ostatni incydent", "contain latest autonomous incident")),
            ("b69_scan", ("skan incydentów", "skan incydentow", "run autonomous incident scan")),
            ("b69_stop", ("zatrzymaj monitor incydentów", "zatrzymaj monitor incydentow", "zatrzymaj centrum incydentów", "zatrzymaj centrum incydentow", "stop autonomous incident monitor")),
            ("b69_pause", ("wstrzymaj monitor incydentów", "wstrzymaj monitor incydentow", "wstrzymaj centrum incydentów", "wstrzymaj centrum incydentow", "pause autonomous incident monitor")),
            ("b69_resume", ("wznów monitor incydentów", "wznow monitor incydentow", "wznów centrum incydentów", "wznow centrum incydentow", "resume autonomous incident monitor")),
            ("b69_start", ("uruchom monitor incydentów", "uruchom monitor incydentow", "uruchom centrum incydentów", "uruchom centrum incydentow", "start autonomous incident monitor")),
            ("b69_history", ("historia incydentów autonomii", "historia incydentow autonomii")),
            ("b69_status", ("status centrum incydentów", "status centrum incydentow", "status incydentów autonomii", "status incydentow autonomii", "status b69", "autonomous incident response status")),
            ("b70_execute", ("wykonaj bezpieczne odzyskiwanie", "execute safe autonomous recovery")),
            ("b70_verify", ("zweryfikuj odzyskiwanie", "verify autonomous recovery")),
            ("b70_plan", ("przygotuj plan odzyskiwania", "zbuduj plan odzyskiwania", "prepare autonomous recovery plan")),
            ("b70_cycle", ("cykl odzyskiwania", "run autonomous recovery cycle")),
            ("b70_stop", ("zatrzymaj odzyskiwanie autonomii", "zatrzymaj orkiestrator odzyskiwania", "zatrzymaj nadzorcę odzyskiwania", "zatrzymaj nadzorce odzyskiwania", "stop autonomous recovery supervisor")),
            ("b70_pause", ("wstrzymaj odzyskiwanie autonomii", "wstrzymaj orkiestrator odzyskiwania", "pause autonomous recovery supervisor")),
            ("b70_resume", ("wznów odzyskiwanie autonomii", "wznow odzyskiwanie autonomii", "wznów orkiestrator odzyskiwania", "wznow orkiestrator odzyskiwania", "resume autonomous recovery supervisor")),
            ("b70_start", ("uruchom odzyskiwanie autonomii", "uruchom autonomiczne odzyskiwanie", "uruchom orkiestrator odzyskiwania", "uruchom nadzorcę odzyskiwania", "uruchom nadzorce odzyskiwania", "start autonomous recovery supervisor")),
            ("b70_history", ("historia odzyskiwania autonomii", "autonomous recovery history")),
            ("b70_status", ("status odzyskiwania autonomii", "status odzyskiwania jarvisa", "status orkiestratora odzyskiwania", "status b70", "autonomous recovery status")),
        )
        for action, phrases in checks:
            if any(phrase in normalized for phrase in phrases):
                return action
        mapping = {
            "b62_cycle": "b62_cycle", "b62_status": "b62_status",
            "b63_cycle": "b63_cycle", "b63_status": "b63_status",
            "b64_status": "b64_status", "b65_cycle": "b65_cycle",
            "b65_status": "b65_status", "b66_create": "b66_create",
            "b66_status": "b66_status", "b67_scan": "b67_scan",
            "b67_status": "b67_status", "b68_start": "b68_start",
            "b68_stop": "b68_stop", "b68_pause": "b68_pause",
            "b68_resume": "b68_resume", "b68_cycle": "b68_cycle",
            "b68_status": "b68_status", "b69_start": "b69_start",
            "b69_stop": "b69_stop", "b69_pause": "b69_pause",
            "b69_resume": "b69_resume", "b69_scan": "b69_scan",
            "b69_status": "b69_status", "b69_history": "b69_history",
            "b69_contain": "b69_contain", "b69_resolve": "b69_resolve",
            "b70_start": "b70_start", "b70_stop": "b70_stop",
            "b70_pause": "b70_pause", "b70_resume": "b70_resume",
            "b70_cycle": "b70_cycle", "b70_plan": "b70_plan",
            "b70_execute": "b70_execute", "b70_verify": "b70_verify",
            "b70_status": "b70_status", "b70_history": "b70_history",
            "autonomy_governance_status": "suite_status",
        }
        return mapping.get(operation, "suite_status")

    @staticmethod
    def _target(suite: Any, action: str) -> tuple[Any, str]:
        mapping = {
            "b62_cycle": (suite.safe_policy_deployment, "run_cycle"),
            "b62_rollback": (suite.safe_policy_deployment, "rollback"),
            "b62_history": (suite.safe_policy_deployment, "history"),
            "b62_status": (suite.safe_policy_deployment, "status"),
            "b63_cycle": (suite.goal_governance, "run_cycle"),
            "b63_history": (suite.goal_governance, "history"),
            "b63_status": (suite.goal_governance, "status"),
            "b64_reset": (suite.resource_budget, "reset_failure_circuit"),
            "b64_status": (suite.resource_budget, "status"),
            "b65_cycle": (suite.causal_learning, "run_cycle"),
            "b65_history": (suite.causal_learning, "history"),
            "b65_status": (suite.causal_learning, "status"),
            "b66_create": (suite.release_manager, "create_candidate"),
            "b66_activate": (suite.release_manager, "activate"),
            "b66_prepare_rollback": (suite.release_manager, "prepare_rollback"),
            "b66_restore": (suite.release_manager, "restore_previous"),
            "b66_history": (suite.release_manager, "history"),
            "b66_status": (suite.release_manager, "status"),
            "b67_cleanup": (suite.self_maintenance, "apply_safe_cleanup"),
            "b67_scan": (suite.self_maintenance, "scan"),
            "b67_history": (suite.self_maintenance, "history"),
            "b67_status": (suite.self_maintenance, "status"),
            "b68_cycle": (suite.full_autonomy, "run_cycle"),
            "b68_start": (suite.full_autonomy, "start_background"),
            "b68_stop": (suite.full_autonomy, "stop_background"),
            "b68_pause": (suite.full_autonomy, "pause"),
            "b68_resume": (suite.full_autonomy, "resume"),
            "b68_history": (suite.full_autonomy, "history"),
            "b68_status": (suite.full_autonomy, "status"),
            "b69_start": (suite.incident_response, "start_background"),
            "b69_stop": (suite.incident_response, "stop_background"),
            "b69_pause": (suite.incident_response, "pause"),
            "b69_resume": (suite.incident_response, "resume"),
            "b69_scan": (suite.incident_response, "scan"),
            "b69_status": (suite.incident_response, "status"),
            "b69_history": (suite.incident_response, "history"),
            "b69_contain": (suite.incident_response, "contain_latest"),
            "b69_resolve": (suite.incident_response, "resolve_latest"),
            "b70_start": (suite.recovery_orchestrator, "start_background"),
            "b70_stop": (suite.recovery_orchestrator, "stop_background"),
            "b70_pause": (suite.recovery_orchestrator, "pause"),
            "b70_resume": (suite.recovery_orchestrator, "resume"),
            "b70_cycle": (suite.recovery_orchestrator, "run_cycle"),
            "b70_plan": (suite.recovery_orchestrator, "plan_latest"),
            "b70_execute": (suite.recovery_orchestrator, "execute_latest"),
            "b70_verify": (suite.recovery_orchestrator, "verify_latest"),
            "b70_status": (suite.recovery_orchestrator, "status"),
            "b70_history": (suite.recovery_orchestrator, "history"),
        }
        return mapping.get(action, (suite.full_autonomy, "status"))
