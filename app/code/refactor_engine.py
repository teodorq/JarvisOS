class RefactorEngine:

    def analyze_code(self, code: str):
        lines = code.splitlines()

        notes = []

        if len(lines) > 80:
            notes.append("Funkcja jest długa. Warto ją podzielić.")

        if "except Exception" in code:
            notes.append("Kod łapie ogólny wyjątek Exception.")

        if "print(" in code:
            notes.append("Kod używa print(). W przyszłości warto dodać logger.")

        if not notes:
            notes.append("Nie wykryto oczywistych problemów.")

        return "\n".join(notes)

    def make_safe_header_comment(self, code: str):
        comment = (
            "# TODO JARVIS: funkcja oznaczona do późniejszej analizy.\n"
        )

        if code.startswith("# TODO JARVIS"):
            return code

        return comment + code