from __future__ import annotations
import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from app.ai.continuous_dev.continuous_developer import ContinuousDeveloper
from app.ai.continuous_dev.continuous_development_execution_service import ContinuousDevelopmentExecutionService
from app.ai.evolution.evolution_engine import EvolutionEngine
from app.ai.evolution.evolution_iteration_service import EvolutionIterationService
from app.ai.self_improvement.improvement_brain import ImprovementBrain
from app.ai.self_improvement.improvement_execution_service import ImprovementExecutionService
from app.ai.software_engineer.implementation_executor import ImplementationExecutor
from app.ai.software_engineer.implementation_execution_service import ImplementationExecutionService

class AuditA322WorkflowServicesTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[1]

    def test_large_engine_files_are_reduced(self):
        limits={
            'app/ai/evolution/evolution_engine.py':1350,
            'app/ai/continuous_dev/continuous_developer.py':1000,
            'app/ai/self_improvement/improvement_brain.py':1300,
            'app/ai/software_engineer/implementation_executor.py':600,
        }
        failures=[]
        for rel,limit in limits.items():
            count=len((self.root/rel).read_text(encoding='utf-8').splitlines())
            if count>=limit: failures.append(f'{rel}: {count} >= {limit}')
        self.assertEqual(failures,[], '\n'.join(failures))

    def test_moved_methods_are_thin_wrappers(self):
        checks={
            'app/ai/evolution/evolution_engine.py':('run_iteration','approve'),
            'app/ai/continuous_dev/continuous_developer.py':('run_iteration','_finalize_coordination'),
            'app/ai/self_improvement/improvement_brain.py':('analyze','execute'),
            'app/ai/software_engineer/implementation_executor.py':('execute',),
        }
        failures=[]
        for rel,names in checks.items():
            tree=ast.parse((self.root/rel).read_text(encoding='utf-8'))
            cls=next(
                n for n in tree.body
                if isinstance(n, ast.ClassDef)
                and all(
                    any(
                        isinstance(item, ast.FunctionDef)
                        and item.name == name
                        for item in n.body
                    )
                    for name in names
                )
            )
            methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
            for name in names:
                length=methods[name].end_lineno-methods[name].lineno+1
                if length>18: failures.append(f'{rel}:{name}={length}')
        self.assertEqual(failures,[], '\n'.join(failures))

    def test_services_are_stateless(self):
        services=(EvolutionIterationService(),ContinuousDevelopmentExecutionService(),ImprovementExecutionService(),ImplementationExecutionService())
        self.assertTrue(all(vars(s)=={} for s in services))

    def test_evolution_not_found_behavior_is_preserved(self):
        engine=EvolutionEngine.__new__(EvolutionEngine)
        engine._get_run=MagicMock(return_value=None)
        engine._not_found=MagicMock(return_value={'success':False,'status':'NOT_FOUND'})
        result=engine.run_iteration('missing')
        self.assertEqual(result['status'],'NOT_FOUND')
        engine._not_found.assert_called_once_with('missing')

    def test_continuous_not_found_behavior_is_preserved(self):
        developer=ContinuousDeveloper.__new__(ContinuousDeveloper)
        developer._get_cycle=MagicMock(return_value=None)
        developer._get_state=MagicMock(return_value=None)
        developer._not_found=MagicMock(return_value={'success':False,'status':'NOT_FOUND'})
        result=developer.run_iteration('missing')
        self.assertEqual(result['status'],'NOT_FOUND')

    def test_improvement_empty_objective_behavior_is_preserved(self):
        brain=ImprovementBrain.__new__(ImprovementBrain)
        result=brain.analyze('   ')
        self.assertFalse(result['success'])
        self.assertEqual(result['status'],'FAILED')

    def test_improvement_missing_session_behavior_is_preserved(self):
        brain=ImprovementBrain.__new__(ImprovementBrain)
        brain._sessions={}
        result=brain.execute('missing')
        self.assertEqual(result['status'],'NOT_FOUND')

    def test_implementation_invalid_task_behavior_is_preserved(self):
        executor=ImplementationExecutor.__new__(ImplementationExecutor)
        executor._normalize_task=MagicMock(return_value={})
        executor._failure=MagicMock(return_value={'success':False,'status':'INVALID_SCHEDULED_TASK'})
        result=executor.execute(None)
        self.assertEqual(result['status'],'INVALID_SCHEDULED_TASK')

if __name__=='__main__': unittest.main()
