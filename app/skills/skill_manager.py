from app.core.services import services


class SkillManager:

    def __init__(self):
        self.skill_factories = []
        self._register_factories()

    def _register_factories(self):
        self.skill_factories = [
            ("browser", self._browser_skill),
            ("desktop", self._desktop_skill),
            ("vision", self._vision_skill),
            ("memory", self._memory_skill),
            ("system", self._system_skill),
            ("code", self._code_skill),
            ("autodev", self._autodev_skill),
            ("windows", self._windows_skill),
        ]

    def _browser_skill(self):
        from app.skills.browser_skill import BrowserSkill

        return services.get(
            "browser_skill",
            BrowserSkill
        )

    def _desktop_skill(self):
        from app.skills.desktop_skill import DesktopSkill

        return services.get(
            "desktop_skill",
            DesktopSkill
        )

    def _vision_skill(self):
        from app.skills.vision_skill import VisionSkill

        return services.get(
            "vision_skill",
            VisionSkill
        )

    def _memory_skill(self):
        from app.skills.memory_skill import MemorySkill

        return services.get(
            "memory_skill",
            MemorySkill
        )

    def _system_skill(self):
        from app.skills.system_skill import SystemSkill

        return services.get(
            "system_skill",
            SystemSkill
        )

    def _code_skill(self):
        from app.skills.code_skill import CodeSkill

        return services.get(
            "code_skill",
            CodeSkill
        )

    def _autodev_skill(self):
        from app.skills.autodev_skill import AutoDevSkill

        return services.get(
            "autodev_skill",
            AutoDevSkill
        )

    def _windows_skill(self):
        from app.skills.windows_skill import WindowsSkill

        return services.get(
            "windows_skill",
            WindowsSkill
        )

    def execute(self, action):
        for name, factory in self.skill_factories:
            skill = factory()

            if skill.can_handle(action):
                return skill.execute(action)

        return None

    def can_handle(self, action):
        for name, factory in self.skill_factories:
            skill = factory()

            if skill.can_handle(action):
                return True

        return False

    def list_skills(self):
        return [
            name
            for name, factory in self.skill_factories
        ]