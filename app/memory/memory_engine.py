from app.memory.memory import Memory
from app.agent.goal_manager import GoalManager
from app.agent.self_reflection import SelfReflection
from app.vision2.vision_memory import VisionMemory


class MemoryEngine:

    def __init__(self):
        self.memory = Memory()
        self.goal_manager = GoalManager()
        self.reflection = SelfReflection()
        self.vision_memory = VisionMemory()

    def remember_note(self, text):
        return self.memory.remember_note(text)

    def remember_task(self, text):
        return self.memory.add_task(text)

    def remember_history(self, user_text, jarvis_text):
        self.memory.add_history(user_text, jarvis_text)

    def remember_knowledge(self, title, content):
        self.memory.remember_knowledge(title, content)

    def remember_experience(self, goal, success, summary):
        self.memory.remember_experience(
            goal,
            success,
            summary
        )

    def remember_application(self, app_name, info):
        self.memory.remember_application(
            app_name,
            info
        )

    def remember_preference(self, key, value):
        self.memory.set_preference(
            key,
            value
        )

    def remember_screen(self, screen):
        self.vision_memory.remember(screen)

    def remember_gui(self, gui):
        self.vision_memory.remember_gui(gui)

    def remember_element(self, name, element):
        self.vision_memory.remember_element(
            name,
            element
        )

    def get_goal_summary(self):
        return self.goal_manager.summary()

    def get_reflection_summary(self):
        return self.reflection.summary()

    def get_memory_summary(self):
        return self.memory.get_summary()

    def get_screen_summary(self):
        return self.vision_memory.summary()

    def search(self, text):
        return {
            "notes": self.memory.search_notes(text),
            "knowledge": self.memory.search_knowledge(text)
        }

    def summary(self):
        return {
            "memory": self.get_memory_summary(),
            "goal": self.get_goal_summary(),
            "reflection": self.get_reflection_summary(),
            "vision": self.get_screen_summary()
        }