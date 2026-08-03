from __future__ import annotations

from typing import Any

from .director_planner import DirectorPlanner
from .director_state import DirectorState


class DirectorExecutionService:
    """Bezstanowa obsługa iteracji i delegacji silnika."""

    def run_iteration(self, engine: Any, director_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        state = engine._get_state(director_id)
        if state is None:
            return {'success': False, 'status': 'NOT_FOUND', 'director_id': director_id}
        if not state.can_continue():
            return engine._finish_session(state=state, status=state.status if state.is_terminal() else 'COMPLETED')
        try:
            state.increment_iteration()
            module_result = engine._execute_selected_module(state=state, context=context)
            success = bool(module_result.get('success', False))
            status = str(module_result.get('status', 'UNKNOWN')).upper()
            state.add_result(module=state.selected_module, status=status, result=module_result, success=success)
            if success:
                state.add_lesson(f'Moduł {state.selected_module} zakończył wykonanie bez błędu.')
                if status in {'WAITING_FOR_APPROVAL', 'WAITING', 'PAUSED'}:
                    state.set_status(status, 'MODULE_WAITING')
                    return engine._build_result(state=state, success=True, status=status, module_result=module_result)
                return engine._finish_session(state=state, status='COMPLETED', module_result=module_result)
            error = str(module_result.get('error', 'Wybrany moduł zakończył operację błędem.'))
            state.add_error(error)
            return engine._finish_session(state=state, status='FAILED', module_result=module_result)
        except Exception as exc:
            state.add_error(str(exc))
            return engine._finish_session(state=state, status='FAILED', module_result={'success': False, 'status': 'FAILED', 'error': str(exc)})

    def _execute_selected_module(self, engine: Any, state: DirectorState, context: dict[str, Any] | None) -> dict[str, Any]:
        command = state.objective
        execution_context = {'project_root': engine.project_root, 'director_id': state.director_id, 'iteration': state.iteration, 'metadata': {'source': 'DirectorEngine'}, **engine._safe_dict(context)}
        module = state.selected_module
        if module == DirectorPlanner.MODULE_RESEARCH:
            if engine.research_service is None:
                return engine._missing_module(module)
            return engine._normalize_result(engine.research_service.execute(command))
        if module == DirectorPlanner.MODULE_REASONER:
            if engine.reasoning_service is None:
                return engine._missing_module(module)
            return engine._normalize_result(engine.reasoning_service.handle(command=command, context=execution_context))
        if module == DirectorPlanner.MODULE_SELF_IMPROVEMENT:
            if engine.improvement_controller is None:
                return engine._missing_module(module)
            improvement_command = command
            if not command.lower().startswith(('self improvement ', 'improvement brain ', 'samodoskonalenie ')):
                improvement_command = 'self improvement analyze ' + command
            return engine._normalize_result(engine.improvement_controller.handle(command=improvement_command, context=execution_context))
        if module == DirectorPlanner.MODULE_EVOLUTION:
            if engine.evolution_controller is None:
                return engine._missing_module(module)
            evolution_command = command
            if not command.lower().startswith(('evolution ', 'auto evolution ', 'ewolucja ')):
                evolution_command = 'evolution start ' + command
            return engine._normalize_result(engine.evolution_controller.handle(command=evolution_command, context=execution_context))
        if module == DirectorPlanner.MODULE_CONTINUOUS_DEV:
            if engine.continuous_dev_controller is None:
                return engine._missing_module(module)
            return engine._normalize_result(engine.continuous_dev_controller.handle(command=command, context=execution_context))
        return {'success': False, 'status': 'NO_ACTION', 'error': 'Project Director nie wybrał obsługiwanego modułu.'}
