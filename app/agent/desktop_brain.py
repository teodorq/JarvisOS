from app.agent.action_history import ActionHistory
from app.agent.desktop_agent import DesktopAgent


class DesktopBrain:

    def __init__(self):

        self.desktop = DesktopAgent()
        self.history = ActionHistory()

    def execute(self, func, *args):

        method = getattr(self.desktop, func)

        result = method(*args)

        self.history.add(
            func,
            result,
            True
        )

        return result

    def history_summary(self):
        return self.history.summary()