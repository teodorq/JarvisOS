from __future__ import annotations

from typing import Any


class ContinuousDevCommandRouter:
    """Bezstanowy router poleceń kontrolera."""

    def handle(self, controller: Any, command: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        normalized_command = str(command).strip()
        if not normalized_command:
            return {'success': False, 'status': 'EMPTY_COMMAND', 'error': 'Polecenie Continuous Developer jest puste.'}
        lowered = normalized_command.lower()
        if lowered.startswith('continuous dev autonomous '):
            objective = normalized_command[len('continuous dev autonomous '):].strip()
            return controller.create_and_start(objective=objective, auto_approve=True, context=context, metadata={'source': 'ContinuousDevController', 'autonomous': True})
        if lowered.startswith('continuous dev autodev '):
            objective = normalized_command[len('continuous dev autodev '):].strip()
            return controller._delegate_to_autodev(objective=objective, context=context)
        if lowered.startswith('continuous dev start '):
            objective = normalized_command[len('continuous dev start '):].strip()
            return controller.create_and_start(objective=objective, context=context)
        if lowered.startswith('continuous dev create '):
            objective = normalized_command[len('continuous dev create '):].strip()
            return controller.create_cycle(objective=objective)
        if lowered.startswith('continuous dev status '):
            cycle_id = normalized_command[len('continuous dev status '):].strip()
            cycle = controller.get_cycle(cycle_id)
            if cycle is None:
                return {'success': False, 'status': 'NOT_FOUND', 'cycle_id': cycle_id}
            return {'success': True, 'status': 'FOUND', 'cycle_id': cycle_id, 'cycle': cycle}
        if lowered.startswith('continuous dev approve '):
            cycle_id = normalized_command[len('continuous dev approve '):].strip()
            return controller.approve_cycle(cycle_id=cycle_id, approved=True, context=context)
        if lowered.startswith('continuous dev reject '):
            cycle_id = normalized_command[len('continuous dev reject '):].strip()
            return controller.approve_cycle(cycle_id=cycle_id, approved=False, note='Odrzucono z polecenia użytkownika.', context=context)
        if lowered.startswith('continuous dev pause '):
            cycle_id = normalized_command[len('continuous dev pause '):].strip()
            return controller.pause_cycle(cycle_id=cycle_id)
        if lowered.startswith('continuous dev resume '):
            cycle_id = normalized_command[len('continuous dev resume '):].strip()
            return controller.resume_cycle(cycle_id=cycle_id, context=context)
        if lowered.startswith('continuous dev cancel '):
            cycle_id = normalized_command[len('continuous dev cancel '):].strip()
            return controller.cancel_cycle(cycle_id=cycle_id)
        if lowered in {'continuous dev list', 'continuous dev cycles'}:
            return {'success': True, 'status': 'COMPLETED', 'cycles': controller.list_cycles()}
        if lowered in {'continuous dev summary', 'continuous dev system'}:
            return {'success': True, 'status': 'COMPLETED', 'summary': controller.system_summary()}
        return {'success': False, 'status': 'UNKNOWN_COMMAND', 'command': normalized_command, 'error': 'Nie rozpoznano polecenia Continuous Developer.'}
