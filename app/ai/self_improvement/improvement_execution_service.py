from __future__ import annotations

from typing import Any
from uuid import uuid4


class ImprovementExecutionService:
    """Bezstanowa obsługa dużych przepływów wykonawczych."""

    def analyze(self, brain: Any, objective: str, project_context: dict[str, Any] | None=None, auto_execute: bool=False, approved: bool | None=None, mode: str='SAFE_AUTONOMOUS') -> dict[str, Any]:
        from .improvement_brain import (
            ImprovementBrainDecision,
            ImprovementBrainStatus,
        )
        normalized_objective = str(objective).strip()
        if not normalized_objective:
            return {'success': False, 'status': ImprovementBrainStatus.FAILED.value, 'error': 'ImprovementBrain wymaga celu analizy.'}
        session_id = f'improvement_brain_{uuid4().hex}'
        context = brain._safe_dict(project_context)
        state = {'session_id': session_id, 'objective': normalized_objective, 'status': ImprovementBrainStatus.ANALYZING.value, 'decision': ImprovementBrainDecision.NO_ACTION.value, 'proposals': [], 'selected_proposal': {}, 'research': {}, 'reasoning': {}, 'execution': {}, 'lessons': [], 'errors': [], 'warnings': [], 'mode': str(mode).upper()}
        brain._sessions[session_id] = state
        try:
            proposals = brain._generate_proposals(objective=normalized_objective, context=context)
            state['proposals'] = proposals
            if not proposals:
                state['status'] = ImprovementBrainStatus.NO_ACTION.value
                state['decision'] = ImprovementBrainDecision.NO_ACTION.value
                return brain._result(state=state, success=True)
            selected = brain._select_best(proposals)
            state['selected_proposal'] = selected
            state['status'] = ImprovementBrainStatus.DECIDING.value
            research = brain._run_research(objective=normalized_objective, proposal=selected, context=context)
            state['research'] = research
            reasoning = brain._run_reasoning(objective=normalized_objective, proposal=selected, research=research, context=context)
            state['reasoning'] = reasoning
            decision = brain._choose_decision(proposal=selected, reasoning=reasoning, auto_execute=auto_execute)
            state['decision'] = decision
            if decision == ImprovementBrainDecision.WAIT_FOR_APPROVAL.value:
                state['status'] = ImprovementBrainStatus.WAITING_FOR_APPROVAL.value
                if approved is True:
                    return brain.execute(session_id=session_id, approved=True, context=context)
                return brain._result(state=state, success=True)
            if decision == ImprovementBrainDecision.NO_ACTION.value:
                state['status'] = ImprovementBrainStatus.NO_ACTION.value
                return brain._result(state=state, success=True)
            if auto_execute:
                return brain.execute(session_id=session_id, approved=approved, context=context)
            state['status'] = ImprovementBrainStatus.PLANNING.value
            return brain._result(state=state, success=True)
        except Exception as error:
            message = f'ImprovementBrain error: {type(error).__name__}: {error}'
            state['status'] = ImprovementBrainStatus.FAILED.value
            state['errors'] = brain._unique_strings(state['errors'] + [message])
            return brain._result(state=state, success=False)

    def execute(self, brain: Any, session_id: str, approved: bool | None=None, context: dict[str, Any] | None=None) -> dict[str, Any]:
        from .improvement_brain import (
            ImprovementBrainDecision,
            ImprovementBrainStatus,
        )
        state = brain._sessions.get(str(session_id).strip())
        if state is None:
            return {'success': False, 'status': 'NOT_FOUND', 'session_id': session_id, 'error': 'Nie znaleziono sesji ImprovementBrain.'}
        decision = str(state.get('decision', ImprovementBrainDecision.NO_ACTION.value)).upper()
        selected = brain._safe_dict(state.get('selected_proposal', {}))
        normalized_context = brain._safe_dict(context)
        if decision == ImprovementBrainDecision.WAIT_FOR_APPROVAL.value and approved is not True:
            state['status'] = ImprovementBrainStatus.WAITING_FOR_APPROVAL.value
            return brain._result(state=state, success=True)
        state['status'] = ImprovementBrainStatus.EXECUTING.value
        try:
            if decision == ImprovementBrainDecision.START_EVOLUTION.value:
                execution = brain._start_evolution(proposal=selected, context=normalized_context, approved=approved, mode=str(state.get('mode', 'SAFE_AUTONOMOUS')))
            elif decision == ImprovementBrainDecision.START_CONTINUOUS_DEV.value:
                execution = brain._start_continuous_dev(proposal=selected, context=normalized_context, approved=approved)
            elif decision == ImprovementBrainDecision.RUN_RESEARCH.value:
                execution = brain._run_research(objective=str(state.get('objective', '')), proposal=selected, context=normalized_context)
            elif decision == ImprovementBrainDecision.RUN_REASONER.value:
                execution = brain._run_reasoning(objective=str(state.get('objective', '')), proposal=selected, research=brain._safe_dict(state.get('research', {})), context=normalized_context)
            else:
                execution = {'success': True, 'status': 'NO_ACTION'}
            state['execution'] = brain._normalize_result(execution)
            if brain._detect_success(state['execution']):
                state['status'] = ImprovementBrainStatus.LEARNING.value
                brain._learn_from_result(state)
                state['status'] = ImprovementBrainStatus.COMPLETED.value
                return brain._result(state=state, success=True)
            error = brain._extract_error(state['execution'])
            state['errors'] = brain._unique_strings(state['errors'] + [error])
            state['status'] = ImprovementBrainStatus.FAILED.value
            return brain._result(state=state, success=False)
        except Exception as error:
            message = f'ImprovementBrain execute error: {type(error).__name__}: {error}'
            state['errors'] = brain._unique_strings(state['errors'] + [message])
            state['status'] = ImprovementBrainStatus.FAILED.value
            return brain._result(state=state, success=False)
