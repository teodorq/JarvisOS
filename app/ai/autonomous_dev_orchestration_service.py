from __future__ import annotations

from typing import Any


class AutonomousDevOrchestrationService:
    """Bezstanowa orkiestracja poleceń i cykli AutoDev."""

    def handle(self, controller: Any, command: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        normalized_command = str(command).strip()
        normalized = normalized_command.casefold()
        context = dict(context or {})
        if not normalized_command:
            return {'success': False, 'status': 'EMPTY_COMMAND', 'error': 'AutonomousDevController otrzymał puste polecenie.'}
        if controller._is_timed_development_command(normalized):
            duration_seconds = controller._extract_duration_seconds(normalized)
            return controller.start_timed_autonomous_loop(duration_seconds=duration_seconds, context=context)
        if 'stop autodev' in normalized or 'zatrzymaj autodev' in normalized or 'zatrzymaj rozwój projektu' in normalized or ('zatrzymaj rozwoj projektu' in normalized):
            return controller.stop_timed_autonomous_loop()
        if 'decision ranking' in normalized or 'ranking zadań' in normalized or 'ranking zadan' in normalized or ('wybierz najlepsze zadanie' in normalized) or ('najlepsze zadanie autodev' in normalized):
            return controller.decision_report(limit=controller._safe_positive_int(context.get('limit'), 10))
        if 'autonomous loop' in normalized or 'autonomiczna pętla' in normalized or 'autonomiczna petla' in normalized or ('rozwijaj projekt autonomicznie' in normalized) or ('pracuj autonomicznie' in normalized):
            return controller.run_autonomous_loop(max_cycles=controller._safe_positive_int(context.get('max_cycles'), 5), context=context, auto_approve=context.get('auto_approve'), auto_execute=context.get('auto_execute'), stop_on_failure=bool(context.get('stop_on_failure', True)))
        if 'generation cycle' in normalized or 'cykl generowania' in normalized or 'generuj zmianę' in normalized or ('generuj zmiane' in normalized):
            return controller.run_generation_cycle(context=context)
        if 'planning cycle' in normalized or 'cykl planowania' in normalized or 'zaplanuj następne' in normalized or ('zaplanuj nastepne' in normalized):
            return controller.run_planning_cycle(context_by_module=context.get('context_by_module'))
        if 'scan' in normalized or 'skanuj' in normalized or 'analizuj projekt' in normalized:
            return controller.scan_project(context_by_module=context.get('context_by_module'))
        if 'autonomous project plan' in normalized or 'generate project goals' in normalized or 'sam zaplanuj rozwój' in normalized or ('sam zaplanuj rozwoj' in normalized) or ('wygeneruj cele rozwoju' in normalized):
            return controller.generate_autonomous_goals(context=context, limit=controller._safe_positive_int(context.get('limit'), 10))
        if 'health' in normalized or 'diagnostyka' in normalized or 'stan systemu autodev' in normalized:
            return controller.health_report()
        if 'planner status' in normalized or 'plan status' in normalized:
            return {'success': True, 'status': 'PLANNER_STATUS', 'last_scan': controller.last_scan, 'last_planning_cycle': controller.last_planning_cycle, 'last_generation_cycle': controller.last_generation_cycle, 'planner': controller.planner.status()}
        if 'next planned' in normalized or 'następny plan' in normalized or 'nastepny plan' in normalized:
            return controller.planner.next_task()
        if 'status' in normalized:
            return {'success': True, 'status': 'STATUS', 'pipeline': controller.pipeline.status(), 'backlog': controller.backlog_summary(), 'planner': controller.planner.status(), 'last_planning_cycle': controller.last_planning_cycle, 'last_generation_cycle': controller.last_generation_cycle}
        if 'list' in normalized or 'lista' in normalized or 'backlog' in normalized:
            return {'success': True, 'status': 'BACKLOG', 'tasks': controller.list_tasks(), 'summary': controller.backlog_summary(), 'planned_tasks': controller.planner.backlog.list_items()}
        if 'next' in normalized or 'następne zadanie' in normalized or 'nastepne zadanie' in normalized:
            return controller.next_task()
        if 'start' in normalized or 'uruchom' in normalized:
            started = controller.pipeline.start()
            return {'success': True, 'status': 'STARTED' if started else 'ALREADY_RUNNING', 'pipeline': controller.pipeline.status()}
        if 'stop' in normalized or 'zatrzymaj' in normalized:
            stopped = controller.pipeline.stop(wait=False)
            return {'success': True, 'status': 'STOPPED' if stopped else 'ALREADY_STOPPED', 'pipeline': controller.pipeline.status()}
        if 'pause' in normalized or 'wstrzymaj' in normalized:
            paused = controller.pipeline.pause()
            return {'success': paused, 'status': 'PAUSED' if paused else 'NOT_RUNNING', 'pipeline': controller.pipeline.status()}
        if 'resume' in normalized or 'wznów' in normalized or 'wznow' in normalized:
            resumed = controller.pipeline.resume()
            return {'success': resumed, 'status': 'RUNNING' if resumed else 'NOT_PAUSED', 'pipeline': controller.pipeline.status()}
        return controller.queue_goal(goal=normalized_command, source=str(context.get('source', 'Brain')), context=context)

    def run_autonomous_loop(self, controller: Any, *, max_cycles: int=5, context: dict[str, Any] | None=None, auto_approve: bool | None=None, auto_execute: bool | None=None, stop_on_failure: bool=True) -> dict[str, Any]:
        normalized_context = dict(context or {})
        cycles_limit = controller._safe_positive_int(max_cycles, 5)
        approve_changes = controller.policy.auto_approve if auto_approve is None else bool(auto_approve)
        execute_changes = controller.policy.auto_execute if auto_execute is None else bool(auto_execute)
        started_pipeline = False
        if controller.policy.auto_start_pipeline:
            started_pipeline = controller.pipeline.start()
        cycle_results: list[dict[str, Any]] = []
        completed_cycles = 0
        loop_status = 'COMPLETED'
        success = True
        blocking_reason = ''
        for cycle_number in range(1, cycles_limit + 1):
            controller.last_planning_cycle = None
            controller.last_generation_cycle = None
            generation = controller.run_generation_cycle(context=normalized_context)
            cycle_result: dict[str, Any] = {'cycle': cycle_number, 'generation': generation}
            generation_status = str(generation.get('status', 'UNKNOWN')).upper()
            if generation_status == 'NO_TASKS':
                loop_status = 'NO_TASKS'
                cycle_results.append(cycle_result)
                break
            if generation_status == 'CODE_INPUT_REQUIRED':
                loop_status = 'WAITING_FOR_CODE_INPUT'
                blocking_reason = 'Planner nie dostarczył kompletnego kodu potrzebnego do utworzenia patcha.'
                cycle_results.append(cycle_result)
                break
            if not generation.get('success', False):
                success = False
                loop_status = 'GENERATION_FAILED'
                blocking_reason = str(generation.get('message', generation.get('error', '')))
                cycle_results.append(cycle_result)
                if stop_on_failure:
                    break
                continue
            if not approve_changes:
                loop_status = 'WAITING_FOR_APPROVAL'
                blocking_reason = 'Automatyczna akceptacja jest wyłączona.'
                cycle_results.append(cycle_result)
                break
            execution = controller.approve_generated_change(auto_execute=execute_changes)
            cycle_result['execution'] = execution
            cycle_results.append(cycle_result)
            execution_status = str(execution.get('status', 'UNKNOWN')).upper()
            if not execute_changes:
                loop_status = 'APPROVED_NOT_EXECUTED'
                blocking_reason = 'Zmiana została zatwierdzona, ale automatyczne wykonanie jest wyłączone.'
                break
            if execution.get('success', False):
                completed_cycles += 1
                continue
            success = False
            loop_status = execution_status if execution_status else 'EXECUTION_FAILED'
            execution_errors = controller._collect_execution_errors(execution)
            blocking_reason = str(execution.get('message', execution.get('error', ''))).strip()
            if execution_errors:
                detailed_errors = '; '.join(execution_errors)
                if blocking_reason:
                    blocking_reason = f'{blocking_reason} | {detailed_errors}'
                else:
                    blocking_reason = detailed_errors
            if stop_on_failure:
                break
        else:
            loop_status = 'MAX_CYCLES_REACHED'
        result = {'success': success, 'status': loop_status, 'max_cycles': cycles_limit, 'completed_cycles': completed_cycles, 'cycles_attempted': len(cycle_results), 'auto_approve': approve_changes, 'auto_execute': execute_changes, 'stop_on_failure': bool(stop_on_failure), 'pipeline_started': started_pipeline, 'blocking_reason': blocking_reason, 'cycles': cycle_results, 'pipeline': controller.pipeline.status(), 'backlog': controller.backlog_summary()}
        controller.last_autonomous_loop = dict(result)
        controller._remember_learning(success=success, status=loop_status, lessons=[f'Autonomiczna pętla wykonała {completed_cycles} pełnych cykli.'], metadata={'stage': 'autonomous_loop', 'cycles_attempted': len(cycle_results), 'max_cycles': cycles_limit})
        return result

    def _collect_execution_errors(self, controller: Any, execution: dict[str, Any]) -> list[str]:
        collected: list[str] = []

        def add_value(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                normalized = value.strip()
                if normalized:
                    collected.append(normalized)
                return
            if isinstance(value, list):
                for item in value:
                    add_value(item)
                return
            if isinstance(value, dict):
                for key in ('error', 'errors', 'message', 'output', 'stderr', 'stdout'):
                    if key in value:
                        add_value(value.get(key))
                for key in ('execution_result', 'validation', 'tests', 'rollback', 'data'):
                    nested = value.get(key)
                    if isinstance(nested, (dict, list)):
                        add_value(nested)
        add_value(execution.get('errors'))
        add_value(execution.get('error'))
        add_value(execution.get('data'))
        unique: list[str] = []
        seen: set[str] = set()
        for item in collected:
            normalized = ' '.join(item.split())
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized[:1200])
        return unique[:12]

    def run_generation_cycle(self, controller: Any, context: dict[str, Any] | None=None) -> dict[str, Any]:
        context = dict(context or {})
        planning = controller.last_planning_cycle
        if planning is None or planning.get('status') not in {'READY_FOR_CODE_GENERATION', 'GENERATING_PATCH'}:
            planning = controller.run_planning_cycle(context_by_module=context.get('context_by_module'))
        if planning.get('status') not in {'READY_FOR_CODE_GENERATION', 'GENERATING_PATCH'}:
            controller.last_generation_cycle = dict(planning)
            return planning
        task = dict(planning.get('task') or {})
        plan = dict(planning.get('plan') or {})
        proposed_content = str(planning.get('proposed_content', ''))
        if proposed_content:
            context['proposed_content'] = proposed_content
        code_proposal = dict(planning.get('code_proposal') or {})
        if code_proposal:
            context.setdefault('path', str(code_proposal.get('target', code_proposal.get('path', task.get('target', '')))))
            context.setdefault('target', str(code_proposal.get('target', task.get('target', ''))))
            context.setdefault('metadata', {})
            context['metadata'] = {**dict(context.get('metadata', {}) or {}), 'code_proposal_source': 'DeveloperAgent', 'generation_strategy': str(code_proposal.get('strategy', ''))}
        context = controller._prepare_autonomous_code_context(task=task, plan=plan, context=context)
        request = controller._build_developer_request(task=task, plan=plan, context=context)
        valid, errors = request.validate()
        if not valid:
            generation_error = str(context.get('autonomous_generation_error', '')).strip()
            if generation_error:
                errors = [*list(errors), generation_error]
            result = {'success': False, 'status': 'CODE_INPUT_REQUIRED', 'errors': errors, 'task': task, 'plan': plan, 'required': controller._required_code_fields(request.mode)}
            controller.last_generation_cycle = dict(result)
            controller._remember_learning(success=False, status='CODE_INPUT_REQUIRED', task=task, errors=errors, lessons=['Brak danych potrzebnych do wygenerowania patcha.'])
            return result
        controller.developer_controller.reset()
        prepared = controller.developer_controller.prepare(request)
        result = {'success': prepared.success, 'status': prepared.status, 'message': prepared.message, 'preview': prepared.preview, 'errors': list(prepared.errors), 'task': task, 'plan': plan, 'request': {'goal': request.goal, 'target': request.target, 'mode': request.mode, 'path': request.path, 'function_name': request.function_name, 'files_count': len(request.replacements)}}
        if prepared.success:
            task_id = str(task.get('task_id', ''))
            if task_id:
                result['planner_task_id'] = task_id
        controller.last_generation_cycle = dict(result)
        controller._remember_learning(success=prepared.success, status=prepared.status, task=task, errors=list(prepared.errors), lessons=[prepared.message], metadata={'stage': 'prepare', 'preview_ready': bool(prepared.preview)})
        return result

    def _prepare_autonomous_code_context(self, controller: Any, *, task: dict[str, Any], plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        prepared_context = dict(context)
        mode = str(prepared_context.get('mode', 'file')).strip()
        if mode != 'file':
            return prepared_context
        existing_content = str(prepared_context.get('proposed_content', ''))
        if existing_content:
            return prepared_context
        target = str(prepared_context.get('path', prepared_context.get('target', task.get('target', '')))).strip()
        if not target:
            return prepared_context
        instruction = str(prepared_context.get('goal', plan.get('goal', task.get('description', task.get('title', ''))))).strip()
        proposal = controller.code_generator.generate_autonomous_file_improvement(path=target, instruction=instruction)
        if not proposal.get('success', False):
            prepared_context['autonomous_generation_error'] = '; '.join((str(error) for error in proposal.get('errors', [])))
            return prepared_context
        prepared_context['target'] = str(proposal.get('path', target))
        prepared_context['path'] = str(proposal.get('path', target))
        prepared_context['proposed_content'] = str(proposal.get('new_content', ''))
        prepared_context.setdefault('metadata', {})
        prepared_context['metadata'] = {**dict(prepared_context.get('metadata', {})), 'autonomous_code_generation': True, 'generation_strategy': str(proposal.get('strategy', 'safe_python_maintenance'))}
        return prepared_context
