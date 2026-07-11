from app.autodev.change_transaction import ChangeTransaction
from app.autodev.code_generator import CodeGenerator


class PatchGenerator:

    def __init__(self):
        self.code_generator = CodeGenerator()

    def build_file_patch(
        self,
        goal: str,
        target: str,
        path: str,
        proposed_content: str
    ) -> tuple[
        ChangeTransaction | None,
        list[str]
    ]:

        generated = (
            self.code_generator
            .generate_file_replacement(
                path=path,
                instruction=goal,
                proposed_content=proposed_content
            )
        )

        if not generated.get(
            "success",
            False
        ):
            return (
                None,
                generated.get(
                    "errors",
                    ["Nieznany błąd generatora."]
                )
            )

        transaction = ChangeTransaction(
            goal=goal,
            target=target
        )

        transaction.add_change(
            path=generated["path"],
            old_content=generated["old_content"],
            new_content=generated["new_content"]
        )

        return transaction, []

    def build_function_patch(
        self,
        goal: str,
        target: str,
        path: str,
        function_name: str,
        new_function_code: str
    ) -> tuple[
        ChangeTransaction | None,
        list[str]
    ]:

        generated = (
            self.code_generator
            .generate_function_replacement(
                path=path,
                function_name=function_name,
                new_function_code=new_function_code
            )
        )

        if not generated.get(
            "success",
            False
        ):
            return (
                None,
                generated.get(
                    "errors",
                    ["Nieznany błąd generatora."]
                )
            )

        transaction = ChangeTransaction(
            goal=goal,
            target=target
        )

        transaction.add_change(
            path=generated["path"],
            old_content=generated["old_content"],
            new_content=generated["new_content"]
        )

        transaction.metadata[
            "function_name"
        ] = function_name

        return transaction, []