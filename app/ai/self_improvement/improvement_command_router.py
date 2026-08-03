from __future__ import annotations

from typing import Any


class ImprovementCommandRouter:
    """Bezstanowy router poleceń kontrolera."""

    def handle(self, controller: Any, command: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        normalized_command = str(command).strip()
        if not normalized_command:
            return {'success': False, 'status': 'EMPTY_COMMAND', 'error': 'Polecenie Self Improvement jest puste.'}
        lowered = normalized_command.lower()
        normalized_context = controller._safe_dict(context)
        analyze_prefixes = ('self improvement analyze ', 'self improvement start ', 'improvement brain analyze ', 'improvement brain start ', 'samodoskonalenie analizuj ', 'samodoskonalenie start ', 'ulepsz siebie ', 'przeanalizuj własny rozwój ', 'przeanalizuj wlasny rozwoj ')
        for prefix in analyze_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()
                return controller.analyze(objective=objective, project_context=normalized_context, auto_execute=False, mode='SAFE_AUTONOMOUS')
        autonomous_prefixes = ('self improvement autonomous ', 'improvement brain autonomous ', 'samodoskonalenie autonomiczne ', 'autonomicznie ulepsz siebie ')
        for prefix in autonomous_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()
                return controller.analyze(objective=objective, project_context=normalized_context, auto_execute=True, approved=True, mode='AUTONOMOUS')
        safe_auto_prefixes = ('self improvement safe ', 'improvement brain safe ', 'bezpiecznie ulepsz siebie ')
        for prefix in safe_auto_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()
                return controller.analyze(objective=objective, project_context=normalized_context, auto_execute=True, approved=None, mode='SAFE_AUTONOMOUS')
        execute_prefixes = ('self improvement execute ', 'improvement brain execute ', 'samodoskonalenie wykonaj ')
        for prefix in execute_prefixes:
            if lowered.startswith(prefix):
                session_id = normalized_command[len(prefix):].strip()
                return controller.execute_session(session_id=session_id, approved=None, context=normalized_context)
        approve_prefixes = ('self improvement approve ', 'improvement brain approve ', 'samodoskonalenie zaakceptuj ')
        for prefix in approve_prefixes:
            if lowered.startswith(prefix):
                session_id = normalized_command[len(prefix):].strip()
                return controller.approve_session(session_id=session_id, approved=True, context=normalized_context)
        reject_prefixes = ('self improvement reject ', 'improvement brain reject ', 'samodoskonalenie odrzuć ', 'samodoskonalenie odrzuc ')
        for prefix in reject_prefixes:
            if lowered.startswith(prefix):
                session_id = normalized_command[len(prefix):].strip()
                return controller.approve_session(session_id=session_id, approved=False, context=normalized_context)
        status_prefixes = ('self improvement status ', 'improvement brain status ', 'samodoskonalenie status ')
        for prefix in status_prefixes:
            if lowered.startswith(prefix):
                session_id = normalized_command[len(prefix):].strip()
                session = controller.get_session(session_id)
                if session is None:
                    return {'success': False, 'status': 'NOT_FOUND', 'session_id': session_id}
                return {'success': True, 'status': 'FOUND', 'session_id': session_id, 'session': session}
        if lowered in {'self improvement list', 'improvement brain list', 'samodoskonalenie lista'}:
            return {'success': True, 'status': 'COMPLETED', 'sessions': controller.list_sessions()}
        if lowered in {'self improvement summary', 'improvement brain summary', 'samodoskonalenie podsumowanie'}:
            return {'success': True, 'status': 'COMPLETED', 'summary': controller.system_summary()}
        if lowered in {'self improvement memory', 'improvement brain memory', 'samodoskonalenie pamięć', 'samodoskonalenie pamiec'}:
            return {'success': True, 'status': 'COMPLETED', 'memory_summary': controller.memory_summary()}
        return {'success': False, 'status': 'UNKNOWN_COMMAND', 'command': normalized_command, 'error': 'Nie rozpoznano polecenia Self Improvement.'}
