from __future__ import annotations

from typing import Any


class EvolutionCommandRouter:
    """Bezstanowy router poleceń kontrolera."""

    def handle(self, controller: Any, command: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        normalized_command = str(command).strip()
        if not normalized_command:
            return {'success': False, 'status': 'EMPTY_COMMAND', 'error': 'Polecenie Evolution Engine jest puste.'}
        lowered = normalized_command.lower()
        start_prefixes = ('evolution start ', 'auto evolution start ', 'ewolucja start ', 'uruchom ewolucję ', 'uruchom ewolucje ')
        for prefix in start_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()
                return controller.create_and_start(objective=objective, mode='SAFE_AUTONOMOUS', context=context)
        autonomous_prefixes = ('evolution autonomous ', 'auto evolution autonomous ', 'ewolucja autonomiczna ')
        for prefix in autonomous_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()
                return controller.create_and_start(objective=objective, mode='AUTONOMOUS', context=context)
        create_prefixes = ('evolution create ', 'auto evolution create ', 'ewolucja utwórz ', 'ewolucja utworz ')
        for prefix in create_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()
                return controller.create_run(objective=objective, context=context)
        continue_prefixes = ('evolution continue ', 'auto evolution continue ', 'ewolucja kontynuuj ')
        for prefix in continue_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                return controller.continue_run(evolution_id=evolution_id, context=context)
        approve_prefixes = ('evolution approve ', 'auto evolution approve ', 'ewolucja zaakceptuj ')
        for prefix in approve_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                return controller.approve_run(evolution_id=evolution_id, approved=True, context=context)
        reject_prefixes = ('evolution reject ', 'auto evolution reject ', 'ewolucja odrzuć ', 'ewolucja odrzuc ')
        for prefix in reject_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                return controller.approve_run(evolution_id=evolution_id, approved=False, note='Odrzucono zmianę z polecenia użytkownika.', context=context)
        pause_prefixes = ('evolution pause ', 'auto evolution pause ', 'ewolucja pauza ')
        for prefix in pause_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                return controller.pause_run(evolution_id=evolution_id)
        resume_prefixes = ('evolution resume ', 'auto evolution resume ', 'ewolucja wznow ', 'ewolucja wznów ')
        for prefix in resume_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                return controller.resume_run(evolution_id=evolution_id, context=context)
        cancel_prefixes = ('evolution cancel ', 'auto evolution cancel ', 'ewolucja anuluj ')
        for prefix in cancel_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                return controller.cancel_run(evolution_id=evolution_id)
        status_prefixes = ('evolution status ', 'auto evolution status ', 'ewolucja status ')
        for prefix in status_prefixes:
            if lowered.startswith(prefix):
                evolution_id = normalized_command[len(prefix):].strip()
                run = controller.get_run(evolution_id)
                if run is None:
                    return {'success': False, 'status': 'NOT_FOUND', 'evolution_id': evolution_id}
                return {'success': True, 'status': 'FOUND', 'evolution_id': evolution_id, 'run': run}
        if lowered in {'evolution list', 'auto evolution list', 'ewolucja lista'}:
            return {'success': True, 'status': 'COMPLETED', 'runs': controller.list_runs()}
        if lowered in {'evolution summary', 'auto evolution summary', 'ewolucja podsumowanie'}:
            return {'success': True, 'status': 'COMPLETED', 'summary': controller.system_summary()}
        return {'success': False, 'status': 'UNKNOWN_COMMAND', 'command': normalized_command, 'error': 'Nie rozpoznano polecenia Evolution Engine.'}
