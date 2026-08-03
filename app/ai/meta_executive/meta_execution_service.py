from __future__ import annotations

from typing import Any

from .meta_planner import MetaPlanner
from .meta_state import MetaState


class MetaExecutionService:
    """Bezstanowa obsługa iteracji i delegacji silnika."""

    def run_cycle(self, engine: Any, meta_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        state = engine._get_state(meta_id)
        if state is None:
            return {'success': False, 'status': 'NOT_FOUND', 'meta_id': meta_id}
        if not state.can_continue():
            return engine._finish_session(state=state, status=state.status if state.is_terminal() else 'COMPLETED')
        try:
            state.increment_cycle()
            delegated_result = engine._execute_selected_layer(state=state, context=context)
            success = bool(delegated_result.get('success', False))
            status = str(delegated_result.get('status', 'UNKNOWN')).upper()
            state.add_result(source=state.selected_layer, status=status, result=delegated_result, success=success)
            if success:
                state.add_lesson(f'Warstwa {state.selected_layer} zakończyła delegację bez błędu.')
                if status in {'WAITING_FOR_APPROVAL', 'WAITING', 'PAUSED'}:
                    state.set_status(status, 'DELEGATION_WAITING')
                    return engine._build_result(state=state, success=True, status=status, delegated_result=delegated_result)
                return engine._finish_session(state=state, status='COMPLETED', delegated_result=delegated_result)
            error = str(delegated_result.get('error', 'Delegowana warstwa zakończyła operację błędem.'))
            state.add_error(error)
            return engine._finish_session(state=state, status='FAILED', delegated_result=delegated_result)
        except Exception as exc:
            state.add_error(str(exc))
            return engine._finish_session(state=state, status='FAILED', delegated_result={'success': False, 'status': 'FAILED', 'error': str(exc)})

    def _execute_selected_layer(self, engine: Any, state: MetaState, context: dict[str, Any] | None) -> dict[str, Any]:
        layer = state.selected_layer
        command = state.objective
        execution_context = {'project_root': engine.project_root, 'meta_id': state.meta_id, 'cycle': state.cycle, 'metadata': {'source': 'MetaEngine'}, **engine._safe_dict(context)}
        if layer == MetaPlanner.LAYER_EXECUTIVE_AI:
            if engine.executive_controller is None:
                return engine._missing_layer(layer)
            executive_command = command
            if not command.lower().startswith(('executive ai ', 'executive ', 'ceo ai ')):
                executive_command = 'executive ai start ' + command
            return engine._normalize_result(engine.executive_controller.handle(command=executive_command, context=execution_context))
        if layer == MetaPlanner.LAYER_PROJECT_DIRECTOR:
            if engine.project_director is None:
                return engine._missing_layer(layer)
            director_command = command
            if not command.lower().startswith(('project director ', 'director ', 'dyrektor projektu ')):
                director_command = 'project director start ' + command
            return engine._normalize_result(engine.project_director.handle(command=director_command, context=execution_context))
        if layer == MetaPlanner.LAYER_SELF_IMPROVEMENT:
            if engine.improvement_controller is None:
                return engine._missing_layer(layer)
            improvement_command = command
            if not command.lower().startswith(('self improvement ', 'improvement brain ', 'samodoskonalenie ')):
                improvement_command = 'self improvement analyze ' + command
            return engine._normalize_result(engine.improvement_controller.handle(command=improvement_command, context=execution_context))
        if layer == MetaPlanner.LAYER_EVOLUTION:
            if engine.evolution_controller is None:
                return engine._missing_layer(layer)
            evolution_command = command
            if not command.lower().startswith(('evolution ', 'auto evolution ', 'ewolucja ')):
                evolution_command = 'evolution start ' + command
            return engine._normalize_result(engine.evolution_controller.handle(command=evolution_command, context=execution_context))
        if layer == MetaPlanner.LAYER_CONTINUOUS_DEV:
            if engine.continuous_dev_controller is None:
                return engine._missing_layer(layer)
            return engine._normalize_result(engine.continuous_dev_controller.handle(command=command, context=execution_context))
        if layer == MetaPlanner.LAYER_REASONER:
            if engine.reasoning_service is None:
                return engine._missing_layer(layer)
            return engine._normalize_result(engine.reasoning_service.handle(command=command, context=execution_context))
        if layer == MetaPlanner.LAYER_RESEARCH:
            if engine.research_service is None:
                return engine._missing_layer(layer)
            return engine._normalize_result(engine.research_service.execute(command))
        return {'success': False, 'status': 'NO_ACTION', 'error': 'Meta Executive nie wybrał obsługiwanej warstwy.'}
