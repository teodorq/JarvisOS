from __future__ import annotations

from typing import Any

from .cycle_state import CycleState
from .development_cycle import (
    DevelopmentCycle,
    DevelopmentCycleResult,
    DevelopmentCycleStage,
)


class ContinuousDevelopmentExecutionService:
    """Bezstanowa obsługa dużych przepływów wykonawczych."""

    def run_iteration(self, developer: Any, cycle_id: str, auto_approve: bool=False, context: dict[str, Any] | None=None) -> dict[str, Any]:
        cycle = developer._get_cycle(cycle_id)
        state = developer._get_state(cycle_id)
        if cycle is None or state is None:
            return developer._not_found(cycle_id)
        if not cycle.can_continue():
            return {'success': False, 'status': cycle.status, 'cycle_id': cycle_id, 'error': 'Cykl nie może być kontynuowany.', 'summary': cycle.summary()}
        normalized_context = developer._safe_dict(context)
        try:
            cycle.next_iteration()
            state.next_iteration()
            analysis = developer._analyze_project(objective=cycle.objective, context=normalized_context)
            cycle.set_analysis(analysis)
            state.set_stage(DevelopmentCycleStage.DETECT_IMPROVEMENT.value, progress=0.2)
            previous_cycles = developer.cycle_memory.recent(limit=20)
            detection = developer.improvement_detector.detect(analysis=analysis, project_context=normalized_context, previous_cycles=previous_cycles)
            candidates = detection.get('candidates', [])
            cycle.set_detected_improvements(candidates if isinstance(candidates, list) else [])
            selected = developer.improvement_detector.choose_best(detection)
            if selected is None:
                result = cycle.complete(result=DevelopmentCycleResult.NO_CHANGES.value, report={'success': True, 'status': 'NO_CHANGES', 'message': 'Nie wykryto ulepszeń wymagających wykonania.'})
                state.complete(metadata={'result': 'NO_CHANGES'})
                developer.cycle_memory.remember(cycle=result, result={'success': True, 'result': 'NO_CHANGES'})
                return {'success': True, 'status': 'NO_CHANGES', 'cycle_id': cycle_id, 'cycle': result}
            cycle.select_improvement(selected)
            state.set_current_improvement(selected.get('improvement_id'))
            research = developer._run_research(selected, normalized_context)
            cycle.set_research(research)
            reasoning = developer._run_reasoning(selected, research, normalized_context)
            cycle.set_reasoning(reasoning)
            plan = developer.improvement_planner.build(improvement=selected, research_context=research, reasoning_context=reasoning, project_context=normalized_context)
            cycle.set_plan(plan)
            tasks = developer._enqueue_plan_tasks(cycle_id=cycle_id, plan=plan)
            next_task = developer.task_queue.next_task(cycle_id=cycle_id)
            if next_task is not None:
                state.set_current_task(next_task.get('task_id'))
            cycle.set_stage(DevelopmentCycleStage.PREPARE_PATCH.value)
            coordination = developer.execution_coordinator.coordinate(cycle_id=cycle_id, plan=plan, task=next_task, approved=True if auto_approve else None, context=normalized_context)
            coordination_status = str(coordination.get('status', '')).upper()
            if coordination_status == 'WAITING_FOR_APPROVAL':
                cycle.set_patch({'requires_approval': True, 'coordination': coordination})
                state.wait_for_approval(task_id=next_task.get('task_id') if isinstance(next_task, dict) else None)
                return {'success': True, 'status': 'WAITING_FOR_APPROVAL', 'cycle_id': cycle_id, 'selected_improvement': selected, 'plan': plan, 'tasks': tasks, 'coordination': coordination, 'summary': cycle.summary()}
            return developer._finalize_coordination(cycle=cycle, state=state, coordination=coordination, selected=selected, plan=plan, tasks=tasks, context=normalized_context)
        except Exception as error:
            message = f'ContinuousDeveloper error: {type(error).__name__}: {error}'
            cycle.fail(message)
            state.fail(message)
            developer.cycle_memory.remember(cycle=cycle.to_dict(), result={'success': False, 'status': 'FAILED', 'error': message})
            return {'success': False, 'status': 'FAILED', 'cycle_id': cycle_id, 'error': message, 'summary': cycle.summary()}

    def _finalize_coordination(self, developer: Any, cycle: DevelopmentCycle, state: CycleState, coordination: dict[str, Any], selected: dict[str, Any], plan: dict[str, Any], tasks: list[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
        status = str(coordination.get('status', '')).upper()
        execution = developer._safe_dict(coordination.get('execution', {}))
        validation = developer._safe_dict(coordination.get('validation', {}))
        rollback = developer._safe_dict(coordination.get('rollback', {}))
        report = developer._safe_dict(coordination.get('report', {}))
        if execution:
            cycle.set_execution(execution)
        if validation:
            cycle.set_validation(validation)
        if rollback:
            cycle.set_rollback(rollback)
        if report:
            cycle.set_report(report)
        next_task = developer.task_queue.next_task(cycle_id=cycle.cycle_id)
        if next_task is not None:
            task_id = next_task['task_id']
            started = developer.task_queue.start_task(task_id)
            if status == 'COMPLETED':
                developer.task_queue.complete_task(task_id=task_id, output_data=coordination)
            elif status in {'FAILED', 'ROLLED_BACK'}:
                developer.task_queue.fail_task(task_id=task_id, error=developer._extract_error(coordination), output_data=coordination, retry=False)
            state.set_current_task(task_id)
            if isinstance(started, dict):
                state.set_current_execution(coordination.get('coordination_id'))
        if status == 'COMPLETED':
            completed_cycle = cycle.complete(result=DevelopmentCycleResult.SUCCESS.value, report=report)
            state.complete(metadata={'coordination_status': status})
            memory = developer.cycle_memory.remember(cycle=completed_cycle, result={'success': True, 'status': 'COMPLETED', 'result': 'SUCCESS', 'lessons': report.get('lessons', [])})
            return {'success': True, 'status': 'COMPLETED', 'cycle_id': cycle.cycle_id, 'selected_improvement': selected, 'plan': plan, 'tasks': tasks, 'coordination': coordination, 'memory': memory, 'summary': cycle.summary()}
        if status == 'ROLLED_BACK':
            completed_cycle = cycle.complete(result=DevelopmentCycleResult.ROLLED_BACK.value, report=report)
            state.complete(metadata={'coordination_status': status})
            memory = developer.cycle_memory.remember(cycle=completed_cycle, result={'success': False, 'status': 'ROLLED_BACK', 'result': 'ROLLED_BACK', 'errors': coordination.get('errors', [])})
            return {'success': False, 'status': 'ROLLED_BACK', 'cycle_id': cycle.cycle_id, 'coordination': coordination, 'memory': memory, 'summary': cycle.summary()}
        error = developer._extract_error(coordination)
        cycle.fail(error=error, report=report)
        state.fail(error)
        memory = developer.cycle_memory.remember(cycle=cycle.to_dict(), result={'success': False, 'status': 'FAILED', 'result': 'FAILED', 'error': error})
        return {'success': False, 'status': 'FAILED', 'cycle_id': cycle.cycle_id, 'error': error, 'coordination': coordination, 'memory': memory, 'summary': cycle.summary()}
