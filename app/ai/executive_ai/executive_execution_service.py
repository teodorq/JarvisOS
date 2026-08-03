from __future__ import annotations

from typing import Any

from .executive_planner import ExecutivePlanner
from .executive_state import ExecutiveState


class ExecutiveExecutionService:
    """Bezstanowa obsługa iteracji i delegacji silnika."""

    def run_phase(self, engine: Any, executive_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        state = engine._get_state(executive_id)
        if state is None:
            return {'success': False, 'status': 'NOT_FOUND', 'executive_id': executive_id}
        if not state.can_continue():
            return engine._finish_session(state=state, status=state.status if state.is_terminal() else 'COMPLETED')
        try:
            state.increment_phase()
            delegated_result = engine._execute_delegation(state=state, context=context)
            success = bool(delegated_result.get('success', False))
            status = str(delegated_result.get('status', 'UNKNOWN')).upper()
            state.add_result(source=state.delegated_module, status=status, result=delegated_result, success=success)
            if success:
                state.add_lesson(f'Moduł {state.delegated_module} zakończył delegację bez błędu.')
                if status in {'WAITING_FOR_APPROVAL', 'WAITING', 'PAUSED'}:
                    state.set_status(status, 'DELEGATION_WAITING')
                    return engine._build_result(state=state, success=True, status=status, delegated_result=delegated_result)
                return engine._finish_session(state=state, status='COMPLETED', delegated_result=delegated_result)
            error = str(delegated_result.get('error', 'Delegowany moduł zakończył operację błędem.'))
            state.add_error(error)
            return engine._finish_session(state=state, status='FAILED', delegated_result=delegated_result)
        except Exception as exc:
            state.add_error(str(exc))
            return engine._finish_session(state=state, status='FAILED', delegated_result={'success': False, 'status': 'FAILED', 'error': str(exc)})

    def _execute_delegation(self, engine: Any, state: ExecutiveState, context: dict[str, Any] | None) -> dict[str, Any]:
        module = state.delegated_module
        command = state.objective
        execution_context = {'project_root': engine.project_root, 'executive_id': state.executive_id, 'phase': state.phase, 'metadata': {'source': 'ExecutiveEngine'}, **engine._safe_dict(context)}
        if module == ExecutivePlanner.MODULE_PROJECT_DIRECTOR:
            if engine.project_director is None:
                return engine._missing_module(module)
            director_command = command
            if not command.lower().startswith(('project director ', 'director ', 'autonomous project director ', 'dyrektor projektu ')):
                director_command = 'project director start ' + command
            return engine._normalize_result(engine.project_director.handle(command=director_command, context=execution_context))
        if module == ExecutivePlanner.MODULE_REASONER:
            if engine.reasoning_service is None:
                return engine._missing_module(module)
            return engine._normalize_result(engine.reasoning_service.handle(command=command, context=execution_context))
        if module == ExecutivePlanner.MODULE_RESEARCH:
            if engine.research_service is None:
                return engine._missing_module(module)
            return engine._normalize_result(engine.research_service.execute(command))
        if module == ExecutivePlanner.MODULE_SELF_IMPROVEMENT:
            if engine.improvement_controller is None:
                return engine._missing_module(module)
            improvement_command = command
            if not command.lower().startswith(('self improvement ', 'improvement brain ', 'samodoskonalenie ')):
                improvement_command = 'self improvement analyze ' + command
            return engine._normalize_result(engine.improvement_controller.handle(command=improvement_command, context=execution_context))
        if module == ExecutivePlanner.MODULE_EVOLUTION:
            if engine.evolution_controller is None:
                return engine._missing_module(module)
            evolution_command = command
            if not command.lower().startswith(('evolution ', 'auto evolution ', 'ewolucja ')):
                evolution_command = 'evolution start ' + command
            return engine._normalize_result(engine.evolution_controller.handle(command=evolution_command, context=execution_context))
        if module == ExecutivePlanner.MODULE_CONTINUOUS_DEV:
            if engine.continuous_dev_controller is None:
                return engine._missing_module(module)
            return engine._normalize_result(engine.continuous_dev_controller.handle(command=command, context=execution_context))
        return {'success': False, 'status': 'NO_ACTION', 'error': 'Executive AI nie wybrał obsługiwanego modułu.'}
