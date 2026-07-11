from app.code.code_agent import CodeAgent
from app.skills.base_skill import BaseSkill


class CodeSkill(BaseSkill):

    name = "code"

    def __init__(self):
        self.code = CodeAgent()

    def can_handle(self, action: dict):
        return action.get("action_type") in [
            "PROJECT_SUMMARY",
            "REBUILD_INDEX",
            "FIND_FILE",
            "FIND_CODE",
            "FIND_CLASS",
            "FIND_FUNCTION",
            "SHOW_CLASS",
            "SHOW_FUNCTION",
            "ANALYZE_FUNCTION",
            "DRAFT_MARK_FUNCTION",
            "DRAFT_REPLACE_FUNCTION",
            "SHOW_PATCH",
            "APPROVE_PATCH",
            "APPLY_PATCH",
            "UNDO_PATCH",
            "LIST_BACKUPS",
            "CLEAR_PATCH",
            "CODE_MEMORY",
            "RUN_PROJECT_TEST"
        ]

    def execute(self, action: dict):

        action_type = action.get("action_type")

        if action_type == "PROJECT_SUMMARY":
            return self.code.project_summary()

        if action_type == "REBUILD_INDEX":
            return self.code.rebuild_index()

        if action_type == "FIND_FILE":
            return self.code.find_file(action.get("target", ""))

        if action_type == "FIND_CODE":
            return self.code.find_code(action.get("target", ""))

        if action_type == "FIND_CLASS":
            return self.code.find_class(action.get("target", ""))

        if action_type == "FIND_FUNCTION":
            return self.code.find_function(action.get("target", ""))

        if action_type == "SHOW_CLASS":
            return self.code.show_class(action.get("target", ""))

        if action_type == "SHOW_FUNCTION":
            return self.code.show_function(action.get("target", ""))

        if action_type == "ANALYZE_FUNCTION":
            return self.code.analyze_function(action.get("target", ""))

        if action_type == "DRAFT_MARK_FUNCTION":
            return self.code.draft_mark_function(action.get("target", ""))

        if action_type == "DRAFT_REPLACE_FUNCTION":
            return self.code.draft_replace_function(
                action.get("target", ""),
                action.get("text", "")
            )

        if action_type == "SHOW_PATCH":
            return self.code.show_patch()

        if action_type == "APPROVE_PATCH":
            return self.code.approve_patch()

        if action_type == "APPLY_PATCH":
            return self.code.apply_patch()

        if action_type == "UNDO_PATCH":
            return self.code.undo_patch()

        if action_type == "LIST_BACKUPS":
            return self.code.list_backups()

        if action_type == "CLEAR_PATCH":
            return self.code.clear_patch()

        if action_type == "CODE_MEMORY":
            return self.code.code_memory_summary()

        if action_type == "RUN_PROJECT_TEST":
            return self.code.run_project_test()

        return None