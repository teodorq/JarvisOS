from __future__ import annotations

from pathlib import Path
from typing import Any

from app.business.business_edition_service import BusinessEditionService

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomous_incident_response_service import (
    AutonomousIncidentResponseService,
)
from .autonomous_recovery_orchestrator_service import (
    AutonomousRecoveryOrchestratorService,
)
from .autonomous_release_service import AutonomousReleaseService
from .autonomous_release_train_service import AutonomousReleaseTrainService
from .causal_learning_service import CausalLearningService
from .full_autonomy_24x7_service import FullAutonomy24x7Service
from .global_autonomy_watchdog_service import GlobalAutonomyWatchdogService
from .goal_governance_service import GoalGovernanceService
from .long_term_development_memory_service import (
    LongTermDevelopmentMemoryService,
)
from .production_autonomy_24x7_service import ProductionAutonomy24x7Service
from .recovery_execution_controller_service import (
    RecoveryExecutionControllerService,
)
from .recovery_learning_service import RecoveryLearningService
from .resource_budget_service import ResourceBudgetService
from .safe_autonomous_deployment_service import SafeAutonomousDeploymentService
from .safe_policy_deployment_service import SafePolicyDeploymentService
from .security_hardening_service import SecurityHardeningService
from .self_maintenance_service import SelfMaintenanceService
from .unified_autonomy_control_center_service import (
    UnifiedAutonomyControlCenterService,
)


class AutonomyGovernanceSuite:
    """Integrated B62-B79 service registry with legacy-safe status."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
        safe_policy_deployment: SafePolicyDeploymentService,
        goal_governance: GoalGovernanceService,
        resource_budget: ResourceBudgetService,
        causal_learning: CausalLearningService,
        release_manager: AutonomousReleaseService,
        self_maintenance: SelfMaintenanceService,
        full_autonomy: FullAutonomy24x7Service,
        incident_response: AutonomousIncidentResponseService,
        recovery_orchestrator: AutonomousRecoveryOrchestratorService | Any | None = None,
        recovery_execution: RecoveryExecutionControllerService | Any | None = None,
        recovery_learning: RecoveryLearningService | Any | None = None,
        control_center: UnifiedAutonomyControlCenterService | Any | None = None,
        global_watchdog: GlobalAutonomyWatchdogService | Any | None = None,
        safe_deployment: SafeAutonomousDeploymentService | Any | None = None,
        release_train: AutonomousReleaseTrainService | Any | None = None,
        development_memory: LongTermDevelopmentMemoryService | Any | None = None,
        security_hardening: SecurityHardeningService | Any | None = None,
        production_autonomy: ProductionAutonomy24x7Service | Any | None = None,
        business_edition: BusinessEditionService | Any | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.store = store
        self.safe_policy_deployment = safe_policy_deployment
        self.goal_governance = goal_governance
        self.resource_budget = resource_budget
        self.causal_learning = causal_learning
        self.release_manager = release_manager
        self.self_maintenance = self_maintenance
        self.full_autonomy = full_autonomy
        self.incident_response = incident_response
        self.recovery_orchestrator = recovery_orchestrator
        self.recovery_execution = recovery_execution
        self.recovery_learning = recovery_learning
        self.control_center = control_center
        self.global_watchdog = global_watchdog
        self.safe_deployment = safe_deployment
        self.release_train = release_train
        self.development_memory = development_memory
        self.security_hardening = security_hardening
        self.production_autonomy = production_autonomy
        self.business_edition = business_edition

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "AUTONOMY_GOVERNANCE_SUITE_STATUS",
            "operation": "autonomy_governance_suite",
            "stage": "B62-B69",
            "suite_span": "B62-B70",
            "extended_suite_span": "B62-B79",
            "runtime": self.store.runtime("B68"),
            "policy": self.store.policy("B68"),
            "summary": self.store.summary("B68"),
            "stage_summaries": {
                stage: self.store.summary(stage)
                for stage in tuple(f"B{value}" for value in range(62, 80))
            },
            "report_path": str(self.store.path),
            "errors": [],
        }


def bootstrap_autonomy_governance_suite(
    controller: Any,
    *,
    strategic_policy_validation: Any,
) -> AutonomyGovernanceSuite:
    suite = getattr(controller, "autonomy_governance_suite", None)
    if suite is not None:
        suite.store.compact()
        return suite

    project_root = controller.project_root
    store = AutonomyGovernanceStore(project_root)
    store.compact()
    evolution = strategic_policy_validation.strategic_policy_evolution
    portfolio = strategic_policy_validation.strategic_portfolio
    execution = strategic_policy_validation.strategic_execution
    development = execution.strategic_development
    project_intelligence = execution.project_intelligence
    self_directed = execution.self_directed

    resource_budget = ResourceBudgetService(project_root, store=store)
    safe_deployment_policy = SafePolicyDeploymentService(
        project_root,
        store=store,
        strategic_policy_validation=strategic_policy_validation,
    )
    goal_governance = GoalGovernanceService(
        project_root,
        store=store,
        strategic_development=development,
        strategic_portfolio=portfolio,
    )
    causal_learning = CausalLearningService(
        project_root,
        store=store,
        strategic_execution=execution,
        safe_policy_deployment=safe_deployment_policy,
    )
    release_manager = AutonomousReleaseService(
        project_root,
        store=store,
        strategic_execution=execution,
    )
    self_maintenance = SelfMaintenanceService(project_root, store=store)
    full_autonomy = FullAutonomy24x7Service(
        project_root,
        store=store,
        resource_budget=resource_budget,
        project_intelligence=project_intelligence,
        self_directed=self_directed,
        strategic_development=development,
        strategic_execution=execution,
        strategic_portfolio=portfolio,
        strategic_policy_evolution=evolution,
        strategic_policy_validation=strategic_policy_validation,
        safe_policy_deployment=safe_deployment_policy,
        goal_governance=goal_governance,
        causal_learning=causal_learning,
        release_manager=release_manager,
        self_maintenance=self_maintenance,
    )
    incident_response = AutonomousIncidentResponseService(
        project_root,
        store=store,
        resource_budget=resource_budget,
        full_autonomy=full_autonomy,
    )
    recovery_orchestrator = AutonomousRecoveryOrchestratorService(
        project_root,
        store=store,
        incident_response=incident_response,
        resource_budget=resource_budget,
        full_autonomy=full_autonomy,
    )
    recovery_execution = RecoveryExecutionControllerService(
        project_root,
        store=store,
        recovery_orchestrator=recovery_orchestrator,
    )
    recovery_learning = RecoveryLearningService(project_root, store=store)
    recovery_execution.recovery_learning = recovery_learning
    control_center = UnifiedAutonomyControlCenterService(
        project_root,
        store=store,
    )
    global_watchdog = GlobalAutonomyWatchdogService(
        project_root,
        store=store,
    )
    safe_source_deployment = SafeAutonomousDeploymentService(
        project_root,
        store=store,
        release_manager=release_manager,
    )
    release_train = AutonomousReleaseTrainService(
        project_root,
        store=store,
    )
    development_memory = LongTermDevelopmentMemoryService(
        project_root,
        store=store,
    )
    security_hardening = SecurityHardeningService(
        project_root,
        store=store,
    )
    production_autonomy = ProductionAutonomy24x7Service(
        project_root,
        store=store,
    )
    business_edition = BusinessEditionService(project_root)
    services = {
        "B68": full_autonomy,
        "B69": incident_response,
        "B70": recovery_orchestrator,
        "B71": recovery_execution,
        "B72": recovery_learning,
        "B73": control_center,
        "B74": global_watchdog,
        "B75": safe_source_deployment,
        "B76": release_train,
        "B77": development_memory,
        "B78": security_hardening,
        "B79": production_autonomy,
    }
    control_center.bind_services(services)
    global_watchdog.bind_services(services)
    production_autonomy.bind_services(services)

    suite = AutonomyGovernanceSuite(
        project_root,
        store=store,
        safe_policy_deployment=safe_deployment_policy,
        goal_governance=goal_governance,
        resource_budget=resource_budget,
        causal_learning=causal_learning,
        release_manager=release_manager,
        self_maintenance=self_maintenance,
        full_autonomy=full_autonomy,
        incident_response=incident_response,
        recovery_orchestrator=recovery_orchestrator,
        recovery_execution=recovery_execution,
        recovery_learning=recovery_learning,
        control_center=control_center,
        global_watchdog=global_watchdog,
        safe_deployment=safe_source_deployment,
        release_train=release_train,
        development_memory=development_memory,
        security_hardening=security_hardening,
        production_autonomy=production_autonomy,
        business_edition=business_edition,
    )
    controller.autonomy_governance_suite = suite
    controller.safe_policy_deployment_service = safe_deployment_policy
    controller.goal_governance_service = goal_governance
    controller.resource_budget_service = resource_budget
    controller.causal_learning_service = causal_learning
    controller.autonomous_release_service = release_manager
    controller.self_maintenance_service = self_maintenance
    controller.full_autonomy_24x7_service = full_autonomy
    controller.autonomous_incident_response_service = incident_response
    controller.autonomous_recovery_orchestrator_service = recovery_orchestrator
    controller.recovery_execution_controller_service = recovery_execution
    controller.recovery_learning_service = recovery_learning
    controller.unified_autonomy_control_center_service = control_center
    controller.global_autonomy_watchdog_service = global_watchdog
    controller.safe_autonomous_deployment_service = safe_source_deployment
    controller.autonomous_release_train_service = release_train
    controller.long_term_development_memory_service = development_memory
    controller.security_hardening_service = security_hardening
    controller.production_autonomy_24x7_service = production_autonomy
    controller.business_edition_service = business_edition
    strategic_policy_validation.autonomy_governance_suite = suite
    evolution.autonomy_governance_suite = suite
    portfolio.autonomy_governance_suite = suite
    execution.autonomy_governance_suite = suite
    execution.safe_policy_deployment_service = safe_deployment_policy
    full_autonomy.start_if_enabled()
    incident_response.start_if_enabled()
    recovery_orchestrator.start_if_enabled()
    recovery_learning.start_if_enabled()
    global_watchdog.start_if_enabled()
    production_autonomy.start_if_enabled()
    return suite
