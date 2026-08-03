from __future__ import annotations

from typing import Any


class EvolutionIterationService:
    """Bezstanowa obsługa dużych przepływów wykonawczych."""

    def run_iteration(self, engine: Any, evolution_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        from .evolution_engine import (
            EvolutionDecision,
            EvolutionStatus,
        )
        run = engine._get_run(evolution_id)
        if run is None:
            return engine._not_found(evolution_id)
        if run.status in engine.TERMINAL_STATUSES:
            return {'success': False, 'status': run.status, 'evolution_id': evolution_id, 'error': 'Proces ewolucji jest już zakończony.'}
        if run.iteration >= run.max_iterations:
            return engine._complete_run(run=run, status=EvolutionStatus.COMPLETED.value, decision=EvolutionDecision.STOP.value, result={'success': True, 'status': 'COMPLETED', 'message': 'Osiągnięto maksymalną liczbę iteracji.'})
        normalized_context = engine._safe_dict(context)
        run.iteration += 1
        run.status = EvolutionStatus.ANALYZING.value
        run.decision = EvolutionDecision.START_CYCLE.value
        run.updated_at = engine._utc_now()
        engine._add_event(run=run, event_type='ITERATION_STARTED', message=f'Rozpoczęto iterację {run.iteration}.', metadata={'iteration': run.iteration, 'max_iterations': run.max_iterations})
        auto_approve = engine._should_auto_approve(run)
        objective = engine._build_iteration_objective(run)
        try:
            cycle_result = engine.continuous_dev_controller.create_and_start(objective=objective, max_iterations=1, auto_approve=auto_approve, context=normalized_context, metadata={'evolution_id': run.evolution_id, 'evolution_iteration': run.iteration, 'evolution_mode': run.mode})
        except Exception as error:
            return engine._fail_run(run=run, error=f'ContinuousDevController error: {type(error).__name__}: {error}')
        run.last_result = engine._safe_dict(cycle_result)
        cycle_id = engine._optional_string(cycle_result.get('cycle_id'))
        if cycle_id:
            run.continuous_cycle_id = cycle_id
        run.history.append({'iteration': run.iteration, 'timestamp': engine._utc_now(), 'cycle_id': cycle_id, 'result': dict(cycle_result)})
        status = str(cycle_result.get('status', 'UNKNOWN')).upper()
        if status == 'WAITING_FOR_APPROVAL':
            run.status = EvolutionStatus.WAITING_FOR_APPROVAL.value
            run.decision = EvolutionDecision.WAIT_FOR_APPROVAL.value
            run.updated_at = engine._utc_now()
            engine._add_event(run=run, event_type='WAITING_FOR_APPROVAL', message='Proces ewolucji czeka na akceptację zmian.', metadata={'continuous_cycle_id': cycle_id})
            engine.save()
            return engine._response(run=run, success=True, result=cycle_result)
        if status == 'NO_CHANGES':
            return engine._complete_run(run=run, status=EvolutionStatus.NO_CHANGES.value, decision=EvolutionDecision.NO_ACTION.value, result=cycle_result)
        if status == 'COMPLETED':
            engine._collect_lessons(run=run, result=cycle_result)
            if run.iteration >= run.max_iterations:
                return engine._complete_run(run=run, status=EvolutionStatus.COMPLETED.value, decision=EvolutionDecision.STOP.value, result=cycle_result)
            run.status = EvolutionStatus.LEARNING.value
            run.decision = EvolutionDecision.CONTINUE.value
            run.updated_at = engine._utc_now()
            engine._add_event(run=run, event_type='ITERATION_COMPLETED', message=f'Iteracja {run.iteration} zakończyła się sukcesem.')
            engine.save()
            return engine._response(run=run, success=True, result=cycle_result)
        if status == 'ROLLED_BACK':
            engine._collect_errors(run=run, result=cycle_result)
            run.status = EvolutionStatus.VALIDATING.value
            run.decision = EvolutionDecision.RETRY.value if run.iteration < run.max_iterations else EvolutionDecision.STOP.value
            run.updated_at = engine._utc_now()
            engine._add_event(run=run, event_type='ROLLED_BACK', message='Zmiana została wycofana. Proces może przygotować nową strategię.')
            engine.save()
            return engine._response(run=run, success=False, result=cycle_result)
        if cycle_result.get('success') is False:
            return engine._fail_run(run=run, error=engine._extract_error(cycle_result), result=cycle_result)
        run.status = EvolutionStatus.PLANNING.value
        run.decision = EvolutionDecision.CONTINUE.value
        run.updated_at = engine._utc_now()
        engine.save()
        return engine._response(run=run, success=True, result=cycle_result)

    def approve(self, engine: Any, evolution_id: str, approved: bool, note: str | None=None, context: dict[str, Any] | None=None) -> dict[str, Any]:
        from .evolution_engine import (
            EvolutionDecision,
            EvolutionStatus,
        )
        run = engine._get_run(evolution_id)
        if run is None:
            return engine._not_found(evolution_id)
        if not run.continuous_cycle_id:
            return {'success': False, 'status': 'NO_CONTINUOUS_CYCLE', 'evolution_id': evolution_id, 'error': 'Brak aktywnego cyklu Continuous Developer.'}
        result = engine.continuous_dev_controller.approve_cycle(cycle_id=run.continuous_cycle_id, approved=approved, note=note, context=engine._safe_dict(context))
        run.last_result = engine._safe_dict(result)
        run.history.append({'iteration': run.iteration, 'timestamp': engine._utc_now(), 'cycle_id': run.continuous_cycle_id, 'approval': {'approved': bool(approved), 'note': note}, 'result': dict(result)})
        if not approved:
            run.status = EvolutionStatus.CANCELLED.value
            run.decision = EvolutionDecision.STOP.value
            run.completed_at = engine._utc_now()
            run.updated_at = run.completed_at
            engine._add_event(run=run, event_type='REJECTED', message='Użytkownik odrzucił proponowaną zmianę.')
            engine.save()
            return engine._response(run=run, success=False, result=result)
        status = str(result.get('status', 'UNKNOWN')).upper()
        if status == 'COMPLETED':
            engine._collect_lessons(run=run, result=result)
            if run.iteration >= run.max_iterations:
                return engine._complete_run(run=run, status=EvolutionStatus.COMPLETED.value, decision=EvolutionDecision.STOP.value, result=result)
            run.status = EvolutionStatus.LEARNING.value
            run.decision = EvolutionDecision.CONTINUE.value
        elif status == 'ROLLED_BACK':
            run.status = EvolutionStatus.VALIDATING.value
            run.decision = EvolutionDecision.RETRY.value
            engine._collect_errors(run=run, result=result)
        elif result.get('success') is False:
            return engine._fail_run(run=run, error=engine._extract_error(result), result=result)
        else:
            run.status = EvolutionStatus.EXECUTING.value
            run.decision = EvolutionDecision.CONTINUE.value
        run.updated_at = engine._utc_now()
        engine.save()
        return engine._response(run=run, success=bool(result.get('success', True)), result=result)
