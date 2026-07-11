from app.ai.commands.base_command import BaseCommand


class CodeCommand(BaseCommand):

    def parse(self, command: str):

        if command == "projekt":
            return self._action("PROJECT_SUMMARY")

        if command == "indeks kodu":
            return self._action("REBUILD_INDEX")

        if command == "pamięć kodu" or command == "pamiec kodu":
            return self._action("CODE_MEMORY")

        if command == "test projektu":
            return self._action("RUN_PROJECT_TEST")

        if command == "backupy kodu":
            return self._action("LIST_BACKUPS")

        if command == "cofnij poprawkę":
            return self._action("UNDO_PATCH")

        if command == "cofnij poprawke":
            return self._action("UNDO_PATCH")

        if command == "pokaż poprawkę":
            return self._action("SHOW_PATCH")

        if command == "pokaz poprawke":
            return self._action("SHOW_PATCH")

        if command == "zatwierdź poprawkę":
            return self._action("APPROVE_PATCH")

        if command == "zatwierdz poprawke":
            return self._action("APPROVE_PATCH")

        if command == "zastosuj poprawkę":
            return self._action("APPLY_PATCH")

        if command == "zastosuj poprawke":
            return self._action("APPLY_PATCH")

        if command == "anuluj poprawkę":
            return self._action("CLEAR_PATCH")

        if command == "anuluj poprawke":
            return self._action("CLEAR_PATCH")

        if command.startswith("znajdź plik "):
            target = command.replace("znajdź plik", "", 1).strip()
            return self._action("FIND_FILE", target=target)

        if command.startswith("znajdź kod "):
            target = command.replace("znajdź kod", "", 1).strip()
            return self._action("FIND_CODE", target=target)

        if command.startswith("znajdź klasę "):
            target = command.replace("znajdź klasę", "", 1).strip()
            return self._action("FIND_CLASS", target=target)

        if command.startswith("znajdz klase "):
            target = command.replace("znajdz klase", "", 1).strip()
            return self._action("FIND_CLASS", target=target)

        if command.startswith("znajdź funkcję "):
            target = command.replace("znajdź funkcję", "", 1).strip()
            return self._action("FIND_FUNCTION", target=target)

        if command.startswith("znajdz funkcje "):
            target = command.replace("znajdz funkcje", "", 1).strip()
            return self._action("FIND_FUNCTION", target=target)

        if command.startswith("pokaż klasę "):
            target = command.replace("pokaż klasę", "", 1).strip()
            return self._action("SHOW_CLASS", target=target)

        if command.startswith("pokaz klase "):
            target = command.replace("pokaz klase", "", 1).strip()
            return self._action("SHOW_CLASS", target=target)

        if command.startswith("pokaż funkcję "):
            target = command.replace("pokaż funkcję", "", 1).strip()
            return self._action("SHOW_FUNCTION", target=target)

        if command.startswith("pokaz funkcje "):
            target = command.replace("pokaz funkcje", "", 1).strip()
            return self._action("SHOW_FUNCTION", target=target)

        if command.startswith("analizuj funkcję "):
            target = command.replace("analizuj funkcję", "", 1).strip()
            return self._action("ANALYZE_FUNCTION", target=target)

        if command.startswith("analizuj funkcje "):
            target = command.replace("analizuj funkcje", "", 1).strip()
            return self._action("ANALYZE_FUNCTION", target=target)

        if command.startswith("oznacz funkcję "):
            target = command.replace("oznacz funkcję", "", 1).strip()
            return self._action("DRAFT_MARK_FUNCTION", target=target)

        if command.startswith("oznacz funkcje "):
            target = command.replace("oznacz funkcje", "", 1).strip()
            return self._action("DRAFT_MARK_FUNCTION", target=target)

        return None

    def _action(
        self,
        action_type,
        target="",
        text="",
        url="",
        query=""
    ):
        return {
            "action_type": action_type,
            "target": target,
            "text": text,
            "url": url,
            "query": query
        }