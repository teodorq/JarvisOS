from __future__ import annotations

import time
from typing import Any

from app.ai.actions import ActionTypes


class BrainCommandRouter:
    """Stateless command planning and execution routing for Brain."""

    def think(self, brain: Any, command: str) -> dict:
        brain.cognitive.before_think(command)
        software_engineer_controller = getattr(brain, 'software_engineer_controller', None)
        if software_engineer_controller is not None and callable(getattr(software_engineer_controller, 'can_handle', None)) and software_engineer_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Zaplanować i bezpiecznie wykonać funkcjonalność przez Autonomous Software Engineer', 'plan': ['Rozbić cel na zadania', 'Zbudować graf zależności', 'Wybrać najlepsze gotowe zadanie', 'Przygotować zmianę kodu', 'Uruchomić walidację i testy', 'Wykonać retry albo rollback', 'Zapisać raport końcowy'], 'actions': [], 'can_execute': True, 'handler': 'autonomous_software_engineer'}
            brain.cognitive.after_plan(thought)
            return thought
        autonomous_controller = getattr(brain, 'autonomous_dev_controller', None)
        if autonomous_controller is not None and callable(getattr(autonomous_controller, 'can_handle', None)) and autonomous_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Uruchomić autonomiczny proces rozwoju JARVIS OS', 'plan': ['Rozpoznać problem lub cel rozwoju', 'Przygotować autonomiczny plan zmian', 'Dodać bezpieczne zadanie do kolejki AutoDev', 'Wygenerować i sprawdzić proponowane zmiany', 'Wykonać testy oraz walidację', 'Wdrożyć zmianę albo wykonać rollback', 'Wygenerować raport końcowy'], 'actions': [], 'can_execute': True, 'handler': 'autonomous_autodev'}
            brain.cognitive.after_plan(thought)
            return thought
        architect_controller = getattr(brain, 'architect_controller', None)
        if architect_controller is not None and callable(getattr(architect_controller, 'can_handle', None)) and architect_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Przeanalizować architekturę JARVIS OS i zaplanować najlepszą refaktoryzację', 'plan': ['Przeskanować kod projektu', 'Zbudować graf zależności', 'Ocenić coupling i cohesion', 'Wykryć problemy architektury', 'Utworzyć blueprinty refaktoryzacji', 'Uszeregować zmiany według ROI i ryzyka', 'Przekazać rekomendacje do Evolution Engine, Project Director i AutoDev'], 'actions': [], 'can_execute': True, 'handler': 'autonomous_architect'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.meta_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Uruchomić lub obsłużyć Meta Executive', 'plan': ['Rozpoznać nadrzędny cel dla całego JARVIS OS', 'Przeanalizować zakres, priorytet i ryzyko', 'Wybrać nadrzędną strategię', 'Wybrać warstwę wykonawczą', 'Delegować cel do Executive AI lub innego modułu', 'Zweryfikować wynik i zapisać wnioski w pamięci Meta Executive'], 'actions': [], 'can_execute': True, 'handler': 'meta_executive'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.executive_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Uruchomić lub obsłużyć Executive AI', 'plan': ['Rozpoznać cel strategiczny dla JARVIS OS', 'Przeanalizować zakres, priorytet i ryzyko', 'Wybrać strategię wykonania', 'Delegować cel do Project Director lub innego modułu', 'Zweryfikować wynik delegowanego działania', 'Zapisać decyzję, wynik i wnioski w pamięci Executive AI'], 'actions': [], 'can_execute': True, 'handler': 'executive_ai'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.director_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Uruchomić lub obsłużyć Autonomous Project Director', 'plan': ['Rozpoznać cel nadrzędnego zarządzania projektem', 'Przeanalizować kontekst oraz stan projektu', 'Wybrać najlepszy moduł wykonawczy', 'Ocenić priorytet, ryzyko i potrzebę akceptacji', 'Uruchomić Research, Reasoner, Self Improvement, Evolution lub Continuous Developer', 'Zweryfikować wynik i zapisać wnioski w pamięci Directora'], 'actions': [], 'can_execute': True, 'handler': 'project_director'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.improvement_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Przeprowadzić analizę Self Improvement Brain', 'plan': ['Rozpoznać cel samodoskonalenia', 'Przeanalizować projekt i możliwe ulepszenia', 'Ocenić priorytet, score oraz confidence', 'Wybrać najlepszą propozycję ulepszenia', 'Przekazać zadanie do Evolution Engine lub Continuous Developer', 'Zapisać wynik i wnioski w pamięci ulepszeń'], 'actions': [], 'can_execute': True, 'handler': 'self_improvement'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.evolution_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Uruchomić lub obsłużyć Auto Evolution Engine', 'plan': ['Rozpoznać polecenie Evolution Engine', 'Utworzyć albo odczytać proces ewolucji', 'Zaplanować iteracje rozwoju projektu', 'Uruchomić bezpieczny proces ewolucji', 'Zapisać wynik, błędy i wnioski w pamięci'], 'actions': [], 'can_execute': True, 'handler': 'evolution'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.continuous_dev_controller.can_handle(command):
            thought = {'command': command, 'goal': 'Uruchomić lub obsłużyć Continuous Developer Loop', 'plan': ['Rozpoznać polecenie Continuous Developer', 'Utworzyć albo odczytać cykl rozwoju', 'Przeprowadzić analizę projektu', 'Wykryć i zaplanować ulepszenie', 'Przekazać zmianę do Research, Reasonera i AutoDev', 'Wykonać walidację oraz rollback w razie błędu'], 'actions': [], 'can_execute': True, 'handler': 'continuous_dev'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.reasoning_service.can_handle(command):
            thought = {'command': command, 'goal': 'Przeprowadzić pełny proces rozumowania AI Reasonera', 'plan': ['Rozpoznać rzeczywisty cel użytkownika', 'Zbudować graf decyzji', 'Wygenerować możliwe strategie', 'Ocenić ryzyko każdej strategii', 'Wybrać najlepszą strategię', 'Przekazać wynik do Research lub AutoDev'], 'actions': [], 'can_execute': True, 'handler': 'reasoner'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.research_service.can_handle(command):
            thought = {'command': command, 'goal': 'Przeprowadzić analizę projektu przez Research Agent', 'plan': ['Rozpoznać cel i kategorię analizy', 'Uruchomić Research Workflow', 'Przeskanować projekt i odczytać kod', 'Wykryć problemy oraz przygotować plan', 'Wygenerować raport Research'], 'actions': [], 'can_execute': True, 'handler': 'research'}
            brain.cognitive.after_plan(thought)
            return thought
        if brain.autodev_router.can_handle(command):
            thought = {'command': command, 'goal': 'Obsłużyć polecenie AutoDev', 'plan': ['Przekazać polecenie do AutoDev Router', 'Wykonać operację AutoDev', 'Wygenerować raport'], 'actions': [], 'can_execute': True, 'handler': 'autodev'}
            brain.cognitive.after_plan(thought)
            return thought
        plan = brain.planner.create_plan(command)
        brain.cognitive.after_plan(plan)
        return {'command': command, 'goal': plan.get('goal', ''), 'plan': plan.get('steps', []), 'actions': plan.get('actions', []), 'can_execute': plan.get('execute', False), 'handler': 'standard'}

    def execute(self, brain: Any, thought: dict) -> Any:
        command = thought.get('command', '')
        handler = thought.get('handler', 'standard')
        if handler == 'autonomous_software_engineer':
            response = brain.software_engineer_controller.handle(command=command, context={'auto_execute': True, 'auto_approve': True, 'auto_rollback': True, 'max_attempts': 3, 'metadata': {'source': 'Brain'}})
            result = brain._format_software_engineer_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'autonomous_autodev':
            response = brain._execute_autonomous_dev(command)
            result = brain._format_autonomous_dev_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'autonomous_architect':
            response = brain.architect_controller.handle(command=command, context={'enqueue': True, 'limit': 10, 'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_architect_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'meta_executive':
            response = brain.meta_controller.handle(command=command, context={'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_meta_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'executive_ai':
            response = brain.executive_controller.handle(command=command, context={'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_executive_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'project_director':
            response = brain.director_controller.handle(command=command, context={'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_project_director_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'self_improvement':
            response = brain.improvement_controller.handle(command=command, context={'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_improvement_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'evolution':
            response = brain.evolution_controller.handle(command=command, context={'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_evolution_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'continuous_dev':
            response = brain.continuous_dev_controller.handle(command=command, context={'project_root': brain.project_root, 'metadata': {'source': 'Brain'}})
            result = brain._format_continuous_dev_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'reasoner':
            response = brain.reasoning_service.handle(command=command, context={'metadata': {'source': 'Brain'}})
            result = brain._format_reasoning_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'research':
            response = brain.research_service.execute(command)
            result = brain._format_research_response(response)
            brain._remember_execution(command, result)
            return result
        if handler == 'autodev':
            result = brain.autodev_router.handle(command)
            brain._remember_execution(command, result)
            return result
        actions = thought.get('actions', [])
        if actions:
            results = []
            for action in actions:
                action_result = brain.executor.execute_action(action)
                results.append(str(action_result))
                if action.get('action_type') == ActionTypes.OPEN_APP:
                    time.sleep(2)
            final_result = ' | '.join(results)
            brain._remember_execution(command, final_result)
            return final_result
        task = brain.task_planner.create_task(command)
        result = brain.agent_loop.run(task)
        brain._remember_execution(command, result)
        return result
