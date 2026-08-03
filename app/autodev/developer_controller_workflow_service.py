from __future__ import annotations

from typing import Any

from app.autodev.developer_request import DeveloperRequest
from app.autodev.workflow_result import WorkflowResult


class DeveloperControllerWorkflowService:
    """Bezstanowe przepływy planowania i wykonania DeveloperController."""

    def enqueue_director_plan(self, controller: Any, objective: str, plan: dict[str, Any], context: dict[str, Any] | None=None) -> dict[str, Any]:
        if controller.task_queue is None:
            return {'success': False, 'status': 'TASK_QUEUE_UNAVAILABLE'}
        normalized_objective = str(objective).strip()
        if not normalized_objective:
            return {'success': False, 'status': 'EMPTY_OBJECTIVE'}
        normalized_plan = dict(plan) if isinstance(plan, dict) else {}
        normalized_context = dict(context) if isinstance(context, dict) else {}
        priority = controller._director_priority(normalized_plan.get('priority'))
        goal = controller.register_goal(title=normalized_objective, description=normalized_objective, priority=priority, tags=['project-director', 'autodev'], metadata={'director_plan_id': normalized_plan.get('plan_id', ''), 'selected_module': normalized_plan.get('selected_module', ''), 'mode': normalized_plan.get('mode', ''), 'context': normalized_context})
        items = controller._director_plan_items(normalized_plan)
        task_ids: list[str] = []
        proposal_to_task: dict[str, str] = {}
        for index, item in enumerate(items, start=1):
            proposal_id = str(item.get('proposal_id', item.get('step_id', index)))
            dependency_ids = [proposal_to_task[dependency] for dependency in item.get('dependencies', []) if dependency in proposal_to_task]
            task = controller.add_goal_task(goal.goal_id, title=str(item.get('title', f'Etap {index}: {normalized_objective}')).strip(), description=str(item.get('description', item.get('instruction', normalized_objective))).strip(), source='project_director', priority=controller._director_priority(item.get('priority', priority)), payload={'director_plan_id': normalized_plan.get('plan_id', ''), 'director_step': item, 'objective': normalized_objective, 'order': item.get('order', index)}, tags=['project-director', 'autodev', str(item.get('subgoal_type', 'step')).lower()], dependencies=dependency_ids)
            proposal_to_task[proposal_id] = task.task_id
            task_ids.append(task.task_id)
        return {'success': True, 'status': 'QUEUED', 'goal_id': goal.goal_id, 'task_ids': task_ids, 'tasks_count': len(task_ids), 'progress': controller.goal_status(goal.goal_id)}

    def prepare(self, controller: Any, request: DeveloperRequest) -> WorkflowResult:
        if not isinstance(request, DeveloperRequest):
            result = WorkflowResult(success=False, status='request_type_invalid', message='Przekazano niepoprawny typ żądania developerskiego.', errors=['Wymagany obiekt DeveloperRequest.'])
            controller.last_result = result
            return result
        if controller.session.status == 'executing':
            result = WorkflowResult(success=False, status='controller_busy', message='Kontroler wykonuje już inną transakcję.', errors=['Poczekaj na zakończenie aktywnej sesji.'])
            controller.last_result = result
            return result
        controller.last_request = request
        request_valid, request_errors = request.validate()
        if not request_valid:
            result = WorkflowResult(success=False, status='request_invalid', message='Żądanie developerskie jest niepoprawne.', errors=request_errors)
            controller.last_result = result
            return result
        controller.session.start(goal=request.goal, target=request.target)
        try:
            transaction, errors = controller._build_transaction(request)
        except Exception as error:
            controller.session.mark_failed(str(error))
            result = WorkflowResult(success=False, status='prepare_failed', message='Nie udało się przygotować transakcji zmian.', errors=[str(error)])
            controller.last_result = result
            return result
        if transaction is None:
            controller.session.mark_failed('Generator nie utworzył transakcji.')
            result = WorkflowResult(success=False, status='patch_generation_failed', message='Nie udało się wygenerować patcha.', errors=errors)
            controller.last_result = result
            return result
        transaction_valid, transaction_errors = transaction.validate()
        if not transaction_valid:
            transaction.mark_failed()
            for error in transaction_errors:
                controller.session.add_note(error)
            controller.session.mark_failed('Transakcja nie przeszła walidacji.')
            result = WorkflowResult(success=False, status='transaction_invalid', message='Wygenerowana transakcja jest niepoprawna.', transaction=transaction, errors=transaction_errors)
            controller.last_result = result
            return result
        if request.metadata:
            transaction.metadata.update(request.metadata)
        transaction.metadata['request_mode'] = request.mode
        transaction.metadata['project_root'] = str(controller.project_root)
        controller.session.set_transaction(transaction)
        preview = controller.patch_preview.build(transaction)
        result = WorkflowResult(success=True, status='waiting_for_approval', message='Patch został przygotowany. Wymagana jest akceptacja.', preview=preview, transaction=transaction, data={'goal': request.goal, 'target': request.target, 'mode': request.mode, 'files': transaction.files(), 'files_count': len(transaction.changes)})
        controller.last_result = result
        return result

    def execute(self, controller: Any, auto_rollback: bool=True) -> WorkflowResult:
        if not controller.session.can_execute():
            result = WorkflowResult(success=False, status='execution_blocked', message='Transakcja nie została zatwierdzona.', transaction=controller.session.transaction, errors=['Wymagany status sesji: approved.', f'Aktualny status sesji: {controller.session.status}'])
            controller.last_result = result
            return result
        transaction = controller.session.transaction
        if transaction is None:
            result = WorkflowResult(success=False, status='missing_transaction', message='Brak transakcji do wykonania.', errors=['DeveloperSession nie posiada transakcji.'])
            controller.last_result = result
            return result
        controller.session.mark_executing()
        try:
            execution_result = controller.executor.execute(transaction=transaction, auto_rollback=auto_rollback)
        except Exception as error:
            controller.session.mark_failed(str(error))
            result = WorkflowResult(success=False, status='execution_exception', message='Wystąpił wyjątek podczas wykonywania zmian.', transaction=transaction, errors=[str(error)])
            controller.last_result = result
            return result
        if execution_result.success:
            controller.session.mark_completed()
            result = WorkflowResult(success=True, status='completed', message='Workflow AutoDev został zakończony powodzeniem.', transaction=transaction, execution_result=execution_result, data={'changed_files': transaction.files(), 'backup_bundle': transaction.backup_bundle_path, 'rollback_used': False})
            controller.last_result = result
            return result
        execution_data = execution_result.data if isinstance(execution_result.data, dict) else {}
        rollback_data = execution_data.get('rollback', {})
        rollback_success = rollback_data.get('success', False) if isinstance(rollback_data, dict) else False
        if rollback_success:
            controller.session.mark_rolled_back()
            status = 'failed_and_rolled_back'
            message = 'Walidacja lub zapis zmian nie powiodły się. Pliki zostały przywrócone.'
        else:
            controller.session.mark_failed(execution_result.message)
            status = 'failed'
            message = 'Workflow AutoDev nie powiódł się.'
        result = WorkflowResult(success=False, status=status, message=message, transaction=transaction, execution_result=execution_result, errors=execution_result.errors, data={'rollback_attempted': bool(rollback_data), 'rollback_success': rollback_success, 'backup_bundle': transaction.backup_bundle_path, 'failure_analysis': controller.validator.analyze_failure(execution_result), 'ai_review': dict(transaction.metadata.get('ai_review', {}) or {}), 'review_retry': dict(transaction.metadata.get('review_retry', {}) or {})})
        controller.last_result = result
        return result
