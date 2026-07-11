from app.agent.task import AgentTask, AgentStep
from app.ai.planner_llm import PlannerLLM
from app.ai.actions import ActionTypes


class TaskPlanner:
    def __init__(self):
        self.planner = PlannerLLM()

    def create_task(self, command: str) -> AgentTask:
        plan = self.planner.create_plan(command)

        task = AgentTask(
            command=command,
            goal=plan.get("goal", command)
        )

        actions = plan.get("actions", [])

        if actions:
            for index, action in enumerate(actions, start=1):
                instruction = self._instruction_from_action(action)

                task.steps.append(
                    AgentStep(
                        index=index,
                        instruction=instruction,
                        action_type=action.get("action_type", ActionTypes.UNKNOWN),
                        target=action.get("target", ""),
                        text=action.get("text", ""),
                        url=action.get("url", ""),
                        query=action.get("query", "")
                    )
                )

            return task

        action_type = plan.get("action_type", ActionTypes.UNKNOWN)
        target = plan.get("target", "")
        text = plan.get("text", "")
        url = plan.get("url", "")
        query = plan.get("query", "")

        steps = plan.get("steps", [])
        if not steps:
            steps = ["Wykonać polecenie"]

        task.steps.append(
            AgentStep(
                index=1,
                instruction=plan.get("goal", steps[0]),
                action_type=action_type,
                target=target,
                text=text,
                url=url,
                query=query
            )
        )

        return task

    def _instruction_from_action(self, action: dict) -> str:
        action_type = action.get("action_type", ActionTypes.UNKNOWN)
        target = action.get("target", "")
        text = action.get("text", "")
        query = action.get("query", "")

        if action_type == ActionTypes.OPEN_APP:
            return f"Otworzyć aplikację: {target}"

        if action_type == ActionTypes.OPEN_WEBSITE:
            return f"Otworzyć stronę: {target}"

        if action_type == ActionTypes.GOOGLE_SEARCH:
            return f"Wyszukać w Google: {query}"

        if action_type == ActionTypes.YOUTUBE_SEARCH:
            return f"Wyszukać na YouTube: {query}"

        if action_type == ActionTypes.TYPE_TEXT:
            return f"Wpisać tekst: {text}"

        if action_type == ActionTypes.PRESS_ENTER:
            return "Nacisnąć Enter"

        if action_type == ActionTypes.VISION_CLICK:
            return f"Kliknąć element: {target}"

        if action_type == ActionTypes.SCREENSHOT:
            return "Zrobić zrzut ekranu"

        if action_type == ActionTypes.VISION_ANALYZE:
            return "Przeanalizować ekran"

        return f"Wykonać akcję: {action_type}"

    def print_task(self, task: AgentTask):
        print("=" * 50)
        print("NOWE ZADANIE")
        print("=" * 50)
        print(task.summary())
        print("=" * 50)