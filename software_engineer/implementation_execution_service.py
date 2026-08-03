from __future__ import annotations

from pathlib import Path
from typing import Any

from app.autodev.developer_request import DeveloperRequest


class ImplementationExecutionService:
    """Bezstanowa obsługa dużych przepływów wykonawczych."""

    def execute(self, executor: Any, scheduled_task: dict[str, Any] | object, *, auto_approve: bool | None=None, auto_rollback: bool | None=None) -> dict[str, Any]:
        normalized = executor._normalize_task(scheduled_task)
        if not normalized:
            return executor._failure(status='INVALID_SCHEDULED_TASK', error='Zadanie musi być słownikiem lub obiektem z to_dict().')
        payload = executor._payload(normalized)
        category = str(normalized.get('category', payload.get('category', ''))).strip().lower()
        if not executor._category_allowed(category):
            return executor._failure(status='NON_CODE_TASK', task=normalized, error='Zadanie nie jest zadaniem implementacyjnym.')
        target = executor._target_path(normalized, payload)
        if not target:
            return executor._failure(status='TARGET_REQUIRED', task=normalized, error='Brak ścieżki docelowej. Dodaj target, path, target_path lub file_path do payload/metadata.')
        target_path = Path(target)
        target_existed = target_path.exists()
        target_error = executor._validate_target(target_path)
        if target_error:
            return executor._failure(status='TARGET_INVALID', task=normalized, error=target_error, extra={'target': target, 'created_new_file': False})
        created_new_file = False
        if not target_existed:
            preparation_error = executor._prepare_new_file(target_path)
            if preparation_error:
                return executor._failure(status='TARGET_PREPARATION_FAILED', task=normalized, error=preparation_error, extra={'target': target, 'created_new_file': False})
            created_new_file = True
        goal = executor._goal(normalized, payload)
        proposed_content = executor._proposed_content(normalized, payload)
        generation: dict[str, Any] = {'used': False, 'success': bool(proposed_content), 'strategy': 'DIRECT_CONTENT', 'errors': []}
        if not proposed_content and executor.policy.allow_code_generation:
            generation = executor._generate_proposal(target=target, goal=goal, normalized=normalized, payload=payload)
            proposed_content = str(generation.get('proposed_content', ''))
        if not proposed_content:
            executor._cleanup_new_file(target_path, created_new_file)
            errors = generation.get('errors', [])
            return executor._failure(status='PROPOSAL_FAILED', task=normalized, error='; '.join((str(item) for item in errors)) or 'Nie wygenerowano kodu.', extra={'generation': generation, 'target': target, 'created_new_file': created_new_file})
        request = DeveloperRequest(goal=goal, target=str(payload.get('module', normalized.get('title', target))), mode='file', path=target, proposed_content=proposed_content, metadata=executor._request_metadata(normalized=normalized, payload=payload, generation=generation))
        approve = executor.policy.auto_approve if auto_approve is None else bool(auto_approve)
        rollback = executor.policy.auto_rollback if auto_rollback is None else bool(auto_rollback)
        try:
            workflow_result = executor.developer_controller.run(request, auto_approve=approve, auto_rollback=rollback)
        except Exception as error:
            executor._cleanup_new_file(target_path, created_new_file)
            return executor._failure(status='EXECUTION_EXCEPTION', task=normalized, error=f'{type(error).__name__}: {error}', extra={'target': target, 'generation': generation, 'created_new_file': created_new_file})
        workflow = executor._workflow_dict(workflow_result)
        workflow_status = str(workflow.get('status', ''))
        mapped_status = executor._status(workflow_status)
        workflow_success = bool(workflow.get('success', False))
        if created_new_file and (not workflow_success) and (mapped_status not in {'PREVIEW_READY', 'APPROVED'}):
            executor._cleanup_new_file(target_path, True)
        return {'success': workflow_success, 'status': mapped_status, 'task_id': str(normalized.get('task_id', payload.get('task_id', ''))), 'target': target, 'goal': goal, 'created_new_file': created_new_file, 'auto_approved': approve, 'auto_rollback': rollback, 'generation': generation, 'request': {'mode': request.mode, 'path': request.path, 'target': request.target}, 'workflow': workflow}
