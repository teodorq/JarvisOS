from __future__ import annotations

from typing import Any

from app.autodev.autonomous_task_queue import AutonomousTask
from app.autodev.developer_request import DeveloperRequest


class AutoDevWorkerRequestService:
    """Bezstanowe budowanie żądań i propozycji kodu AutoDevWorker."""

    def _build_request(self, worker: Any, task: AutonomousTask) -> DeveloperRequest:
        payload = dict(task.payload)
        goal = str(payload.get('goal') or task.description or task.title).strip()
        target = str(payload.get('target') or payload.get('path') or task.title).strip()
        mode = str(payload.get('mode', 'file')).strip()
        code_inputs = worker._resolve_code_inputs(task=task, payload=payload, goal=goal, target=target, mode=mode)
        metadata = dict(payload.get('metadata') or {})
        metadata.setdefault('autodev_task_id', task.task_id)
        metadata.setdefault('autodev_source', task.source)
        metadata.setdefault('autodev_priority', int(task.priority))
        metadata.setdefault('autodev_worker_id', worker.worker_id)
        proposal_metadata = dict(code_inputs.get('metadata', {}) or {})
        metadata.update({str(key): value for key, value in proposal_metadata.items()})
        return DeveloperRequest(goal=goal, target=target, mode=mode, path=str(code_inputs.get('path', payload.get('path', target))), proposed_content=str(code_inputs.get('proposed_content', '')), function_name=str(code_inputs.get('function_name', payload.get('function_name', ''))), new_function_code=str(code_inputs.get('new_function_code', '')), replacements=dict(code_inputs.get('replacements', {}) or {}), metadata=metadata)

    def _resolve_code_inputs(self, worker: Any, *, task: AutonomousTask, payload: dict[str, Any], goal: str, target: str, mode: str) -> dict[str, Any]:
        direct = {'path': str(payload.get('path', target)), 'proposed_content': str(payload.get('proposed_content', '')), 'function_name': str(payload.get('function_name', '')), 'new_function_code': str(payload.get('new_function_code', '')), 'replacements': dict(payload.get('replacements', {}) or {}), 'metadata': {}}
        nested_proposal = worker._find_code_proposal(payload)
        if nested_proposal:
            direct['path'] = str(nested_proposal.get('path', nested_proposal.get('target', direct['path'])))
            direct['proposed_content'] = str(nested_proposal.get('proposed_content', nested_proposal.get('new_content', direct['proposed_content'])))
            direct['function_name'] = str(nested_proposal.get('function_name', direct['function_name']))
            direct['new_function_code'] = str(nested_proposal.get('new_function_code', direct['new_function_code']))
            direct['replacements'] = dict(nested_proposal.get('replacements', direct['replacements']) or {})
            direct['metadata'] = {'code_proposal_source': 'task_payload', 'generation_strategy': str(nested_proposal.get('strategy', ''))}
        needs_generation = mode == 'file' and (not direct['proposed_content'].strip())
        if needs_generation:
            proposal = worker.developer_agent.generate_code_proposal(target=direct['path'] or target, goal=goal, task={'task_id': task.task_id, 'title': task.title, 'description': task.description, 'target': target, 'metadata': dict(payload.get('metadata', {}) or {})})
            if proposal.get('success', False):
                direct['path'] = str(proposal.get('target', proposal.get('path', direct['path'])))
                direct['proposed_content'] = str(proposal.get('proposed_content', proposal.get('new_content', '')))
                direct['metadata'] = {**dict(direct.get('metadata', {})), 'code_proposal_source': 'developer_agent', 'generation_strategy': str(proposal.get('strategy', ''))}
            else:
                errors = list(proposal.get('errors', []) or [])
                if errors:
                    raise ValueError('DeveloperAgent nie wygenerował kodu: ' + '; '.join((str(error) for error in errors)))
        return direct

    def _find_code_proposal(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            if 'proposed_content' in value or 'new_content' in value or 'new_function_code' in value or ('replacements' in value):
                return dict(value)
            for key in ('code_proposal', 'proposal', 'plan', 'developer_plan', 'generation', 'result', 'data', 'context', 'metadata'):
                nested = value.get(key)
                found = self._find_code_proposal(nested)
                if found:
                    return found
            for nested in value.values():
                if not isinstance(nested, (dict, list, tuple)):
                    continue
                found = self._find_code_proposal(nested)
                if found:
                    return found
        if isinstance(value, (list, tuple)):
            for item in value:
                found = self._find_code_proposal(item)
                if found:
                    return found
        return {}
