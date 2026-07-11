from app.agent.task import AgentTask
from app.agent.task_planner import TaskPlanner
from app.agent.task_executor import TaskExecutor


class AutonomousAgent:
    """
    Główny Agent JARVIS OS v2.

    Odpowiada za:
    - planowanie zadań,
    - wykonywanie kroków,
    - kontrolę stanu zadania,
    - historię wykonania.
    """

    def __init__(self):
        self.planner = TaskPlanner()
        self.executor = TaskExecutor()

        self.current_task: AgentTask | None = None

    def start(self, command: str) -> AgentTask:
        """
        Tworzy nowe zadanie.
        """

        self.current_task = self.planner.create_task(command)
        return self.current_task

    def execute(self) -> str:
        """
        Wykonuje całe zadanie.
        """

        if self.current_task is None:
            return "Brak aktywnego zadania."

        return self.executor.execute_all(self.current_task)

    def execute_next(self) -> str:
        """
        Wykonuje tylko następny krok.
        """

        if self.current_task is None:
            return "Brak aktywnego zadania."

        return self.executor.execute_next_step(self.current_task)

    def has_task(self) -> bool:
        return self.current_task is not None

    def is_finished(self) -> bool:
        if self.current_task is None:
            return True

        return self.current_task.finished

    def summary(self) -> str:
        if self.current_task is None:
            return "Brak aktywnego zadania."

        return self.current_task.summary()

    def clear(self):
        self.current_task = None