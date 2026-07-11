from app.automation.command_executor import CommandExecutor
from app.agent.task import AgentTask


class TaskExecutor:

    def __init__(self):
        self.executor = CommandExecutor()

    def execute_next_step(self, task: AgentTask) -> str:
        if task.finished:
            return "Zadanie jest już zakończone."

        step = task.get_current_step()

        if step is None:
            task.finished = True
            return "Brak kolejnego kroku."

        task.mark_step_attempt()

        action = {
            "action_type": step.action_type,
            "target": step.target,
            "text": step.text,
            "url": step.url,
            "query": step.query
        }

        try:
            result = self.executor.execute_action(action)
            step_result = f"Krok {step.index}, próba {step.attempts}: {result}"
            return step_result

        except Exception as error:
            error_text = f"Błąd kroku {step.index}, próba {step.attempts}: {error}"
            task.mark_step_failed(error_text)
            return error_text

    def finish_current_step(self, task: AgentTask, result: str):
        task.mark_step_done(result)

    def retry_current_step(self, task: AgentTask, reason: str = "", next_hint: str = ""):
        task.mark_step_retry(reason, next_hint)

    def fail_current_step(self, task: AgentTask, result: str):
        task.mark_step_failed(result)

    def execute_all(self, task: AgentTask, max_steps: int = 10) -> str:
        results = []

        counter = 0

        while not task.finished and counter < max_steps:
            result = self.execute_next_step(task)
            results.append(result)

            self.finish_current_step(task, result)

            counter += 1

        if counter >= max_steps and not task.finished:
            task.mark_failed("Przekroczono limit kroków.")
            results.append("Przekroczono limit kroków.")

        results.append("")
        results.append("PODSUMOWANIE:")
        results.append(task.summary())

        return "\n".join(results)