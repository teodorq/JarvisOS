import time

from app.agent.goal_manager import GoalManager
from app.agent.replanner import RePlanner
from app.agent.self_reflection import SelfReflection
from app.agent.task import AgentTask
from app.agent.task_executor import TaskExecutor
from app.vision.vision_feedback import VisionFeedback


class AgentLoop:

    def __init__(self):
        self.executor = TaskExecutor()
        self.feedback = VisionFeedback()
        self.replanner = RePlanner()
        self.goal_manager = GoalManager()
        self.reflection = SelfReflection()

    def run(self, task: AgentTask) -> str:
        history = []

        self.goal_manager.start_goal(task.goal)

        while not task.finished:
            step = task.get_current_step()

            if step is None:
                break

            history.append("")
            history.append("=" * 40)
            history.append(f"KROK {step.index}")
            history.append("=" * 40)
            history.append(step.instruction)
            history.append(f"Próba: {step.attempts + 1}/{step.max_attempts}")

            result = self.executor.execute_next_step(task)
            history.append(result)

            if task.failed:
                break

            time.sleep(0.8)

            feedback = self.feedback.check_step(
                step_instruction=step.instruction,
                action_result=result
            )

            step.feedback_success = feedback.get("success", True)
            step.feedback_confidence = feedback.get("confidence", 0.0)
            step.feedback_reason = feedback.get("reason", "")
            step.next_hint = feedback.get("next_hint", "")

            history.append("")
            history.append("VISION FEEDBACK:")
            history.append(f"Success: {step.feedback_success}")
            history.append(f"Confidence: {step.feedback_confidence}")
            history.append(f"Reason: {step.feedback_reason}")
            history.append(f"Next hint: {step.next_hint}")

            if step.feedback_success:
                self.goal_manager.complete_step(step, result)
                self.executor.finish_current_step(task, result)
                time.sleep(0.35)
                continue

            repaired = self.replanner.repair_step(step, feedback)

            if repaired is not None and step.can_retry():
                history.append("")
                history.append("RePlanner zmienił plan.")
                history.append(f"Nowa instrukcja: {step.instruction}")

                self.executor.retry_current_step(
                    task,
                    reason=step.feedback_reason,
                    next_hint=step.next_hint
                )

                time.sleep(0.5)
                continue

            if step.can_retry():
                self.executor.retry_current_step(
                    task,
                    reason=step.feedback_reason,
                    next_hint=step.next_hint
                )

                history.append("")
                history.append(
                    f"Ponawiam próbę "
                    f"{step.attempts}/{step.max_attempts}"
                )

                time.sleep(0.5)
                continue

            self.goal_manager.fail_step(step, step.feedback_reason)

            self.executor.fail_current_step(
                task,
                "Vision Feedback: krok nieudany."
            )

            history.append("")
            history.append("Agent zakończył zadanie niepowodzeniem.")
            break

        if task.failed:
            self.goal_manager.fail_goal()
        else:
            self.goal_manager.finish_goal()

        reflection = self.reflection.reflect(
            task,
            self.goal_manager
        )

        history.append("")
        history.append("=" * 40)
        history.append("GOAL MANAGER")
        history.append("=" * 40)
        history.append(self.goal_manager.summary())

        history.append("")
        history.append("=" * 40)
        history.append("SELF REFLECTION")
        history.append("=" * 40)
        history.append(reflection["summary"])

        history.append("")
        history.append("=" * 40)
        history.append("ZAKOŃCZONO")
        history.append("=" * 40)
        history.append(task.summary())

        return "\n".join(history)