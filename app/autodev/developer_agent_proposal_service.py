from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.autodev.llm_patch_generator import LLMPatchRequest


class DeveloperAgentProposalService:
    """Stateless preparation, generation and review workflow."""

    def prepare_planned_task(self, agent: Any, task: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(task, dict):
            raise TypeError('Planowane zadanie musi być słownikiem.')
        task_id = str(task.get('task_id', '')).strip()
        title = str(task.get('title', '')).strip()
        description = str(task.get('description', '')).strip()
        recommendation = str(task.get('recommendation', '')).strip()
        target = str(task.get('target', '')).strip()
        goal = description or title
        if recommendation:
            goal = f'{goal} Zalecenie: {recommendation}'.strip()
        if not goal:
            raise ValueError('Planowane zadanie nie posiada celu.')
        if not target:
            raise ValueError('Planowane zadanie nie posiada targetu.')
        report = agent.prepare_developer_task(goal_text=goal, target=target)
        proposal = agent.generate_code_proposal(target=target, goal=goal, task=task)
        return {'success': True, 'status': 'CODE_PROPOSAL_READY' if proposal.get('success', False) else 'PLAN_PREPARED', 'task_id': task_id, 'goal': goal, 'target': target, 'priority_score': task.get('priority_score', 0.0), 'severity': task.get('severity', 'MEDIUM'), 'report': report, 'code_proposal': proposal, 'proposed_content': str(proposal.get('proposed_content', '')), 'generation_strategy': str(proposal.get('strategy', ''))}

    def generate_code_proposal(self, agent: Any, *, target: str, goal: str, task: dict[str, Any] | None=None) -> dict[str, Any]:
        task = dict(task or {})
        file_path = agent._resolve_target(target)
        result: dict[str, Any] = {'success': False, 'target': str(file_path), 'goal': str(goal), 'proposed_content': '', 'strategy': '', 'errors': [], 'metadata': {'task_id': str(task.get('task_id', '')), 'title': str(task.get('title', ''))}}
        if not file_path.exists():
            result['errors'].append(f'Plik nie istnieje: {file_path}')
            return result
        if not file_path.is_file():
            result['errors'].append(f'Target nie jest plikiem: {file_path}')
            return result
        if file_path.suffix.casefold() != '.py':
            result['errors'].append('Automatyczne propozycje kodu obsługują obecnie pliki Python.')
            return result
        if not agent._is_safe_target(file_path):
            result['errors'].append('Target znajduje się w chronionym obszarze projektu.')
            return result
        try:
            source = file_path.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(file_path))
        except Exception as error:
            result['errors'].append(f'{type(error).__name__}: {error}')
            return result
        metadata = dict(task.get('metadata') or {})
        if not source.strip():
            proposal = agent._bootstrap_new_python_file(goal=str(goal), title=str(task.get('title', '')), file_path=file_path)
            strategy = 'bootstrap_new_python_file'
        else:
            proposal, strategy = agent._proposal_for_task(source=source, tree=tree, title=str(task.get('title', '')), metadata=metadata)
        if not proposal:
            llm_request = LLMPatchRequest(goal=str(goal), path=str(file_path), issue_type=str(metadata.get('rule', task.get('problem_type', 'GENERAL_IMPROVEMENT'))), strategy='MINIMAL_SAFE_PATCH', source_content=source, constraints=['Zwróć pełną zawartość pliku.', 'Wykonaj najmniejszą bezpieczną zmianę.', 'Zachowaj zgodność z istniejącym API.', 'Nie usuwaj zabezpieczeń AutoDev.'], metadata={'task_id': str(task.get('task_id', '')), 'title': str(task.get('title', ''))})
            llm_result = agent.llm_patch_generator.generate(llm_request)
            if not llm_result.success:
                result['errors'].extend(list(llm_result.errors))
                result['metadata']['llm_status'] = llm_result.status
                return result
            proposal = str(llm_result.proposed_content)
            strategy = 'local_llm_patch'
            result['metadata']['llm_status'] = llm_result.status
            result['metadata']['llm_explanation'] = llm_result.explanation
            result['metadata']['llm_warnings'] = list(llm_result.warnings)
        review = agent.review_code_proposal(source_content=source, proposed_content=proposal, file_path=file_path)
        result['metadata']['ai_review'] = review
        if not review.get('approved', False):
            retry = agent._retry_after_review(file_path=file_path, goal=str(goal), source_content=source, proposal=proposal, review=review, task=task)
            result['metadata']['review_retry'] = {'attempted': True, 'success': bool(retry.get('success', False)), 'status': str(retry.get('status', ''))}
            if retry.get('success', False):
                proposal = str(retry.get('proposed_content', ''))
                strategy = 'local_llm_review_retry'
                review = agent.review_code_proposal(source_content=source, proposed_content=proposal, file_path=file_path)
                result['metadata']['ai_review'] = review
            if not review.get('approved', False):
                result['errors'].extend([str(item) for item in review.get('blocking_reasons', [])])
                return result
        else:
            result['metadata']['review_retry'] = {'attempted': False, 'success': False, 'status': 'NOT_REQUIRED'}
        result['success'] = True
        result['proposed_content'] = proposal
        result['strategy'] = strategy
        return result

    def review_code_proposal(self, agent: Any, *, source_content: str, proposed_content: str, file_path: Path) -> dict[str, Any]:
        blocking_reasons: list[str] = []
        warnings: list[str] = []
        if not proposed_content.strip():
            blocking_reasons.append('AI Code Review: propozycja jest pusta.')
        if proposed_content == source_content:
            blocking_reasons.append('AI Code Review: propozycja nie zmienia pliku.')
        try:
            ast.parse(proposed_content, filename=str(file_path))
        except SyntaxError as error:
            blocking_reasons.append(f'AI Code Review: błąd składni w linii {error.lineno}, kolumnie {error.offset}: {error.msg}')
        source_lines = max(1, len(source_content.splitlines()))
        proposal_lines = len(proposed_content.splitlines())
        if source_content.strip() and proposal_lines < max(3, int(source_lines * 0.45)):
            blocking_reasons.append('AI Code Review: propozycja usuwa zbyt dużą część istniejącego pliku.')
        if source_content.strip() and proposal_lines > int(source_lines * 2.5) + 250:
            warnings.append('AI Code Review: propozycja jest znacznie większa od pliku źródłowego.')
        forbidden_tokens = ('os.system(', 'subprocess.Popen(', 'subprocess.run(', 'eval(', 'exec(', 'shutil.rmtree(', 'winreg.')
        introduced = [token for token in forbidden_tokens if token in proposed_content and token not in source_content]
        if introduced:
            blocking_reasons.append('AI Code Review: wykryto nowe ryzykowne operacje: ' + ', '.join(introduced))
        approved = not blocking_reasons
        return {'approved': approved, 'status': 'APPROVED' if approved else 'REJECTED', 'blocking_reasons': blocking_reasons, 'warnings': warnings, 'source_lines': source_lines, 'proposal_lines': proposal_lines, 'review_version': '1.0'}

    def _retry_after_review(self, agent: Any, *, file_path: Path, goal: str, source_content: str, proposal: str, review: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
        reasons = [str(item) for item in review.get('blocking_reasons', [])]
        retry_request = LLMPatchRequest(goal=f'{goal}\nPopraw poprzednią propozycję zgodnie z wynikiem Code Review.', path=str(file_path), issue_type='CODE_REVIEW_RETRY', strategy='MINIMAL_SAFE_REPAIR', source_content=source_content, constraints=['Zwróć pełną zawartość pliku.', 'Zachowaj istniejące publiczne API.', 'Nie usuwaj działających funkcji.', 'Nie dodawaj ryzykownych operacji.', 'Popraw wszystkie uwagi Code Review: ' + '; '.join(reasons), 'Poprzednia propozycja do poprawy:\n' + proposal[:120000]], metadata={'task_id': str(task.get('task_id', '')), 'retry_reason': 'AI_CODE_REVIEW'})
        retry_result = agent.llm_patch_generator.generate(retry_request)
        return {'success': retry_result.success, 'status': retry_result.status, 'proposed_content': retry_result.proposed_content, 'errors': list(retry_result.errors), 'warnings': list(retry_result.warnings)}

    def _proposal_for_task(self, agent: Any, *, source: str, tree: ast.AST, title: str, metadata: dict[str, Any]) -> tuple[str, str]:
        normalized_title = str(title).casefold()
        rule = str(metadata.get('rule', '')).casefold()
        if rule == 'missing_module_docstring' or 'brak opisu modułu' in normalized_title:
            if ast.get_docstring(tree, clean=False) is None:
                return (agent._add_module_docstring(source, tree), 'add_module_docstring')
        if rule == 'todo_comment' or 'komentarz todo' in normalized_title or 'komentarz fixme' in normalized_title:
            line_number = agent._safe_int(metadata.get('line'))
            if line_number > 0:
                changed = agent._normalize_task_comment(source, line_number)
                if changed != source:
                    return (changed, 'normalize_task_comment')
        if rule == 'empty_except' or 'pusty blok except' in normalized_title:
            line_number = agent._safe_int(metadata.get('line'))
            changed = agent._replace_empty_except(source, tree, line_number)
            if changed != source:
                return (changed, 'replace_empty_except')
        if not source.endswith('\n'):
            return (source + '\n', 'ensure_final_newline')
        if not agent._has_future_annotations(tree):
            return (agent._add_future_annotations(source, tree), 'add_future_annotations')
        return ('', '')
