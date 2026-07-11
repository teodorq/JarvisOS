
     "status",
            response.get(
                "status",
                "UNKNOWN",
            ),
        )

        requires_confirmation = result.get(
            "requires_confirmation",
            strategy.get(
                "requires_confirmation",
                False,
            ),
        )

        blocking_reasons = result.get(
            "blocking_reasons",
            strategy.get(
                "blocking_reasons",
                [],
            ),
        )

        lines = [
            "AI Reasoner zakończył analizę.",
            f"Status: {status}",
            f"Strategia: {strategy_name}",
            f"Poziom ryzyka: {risk_level}",
        ]

        if session_id:
            lines.append(
                f"Session ID: {session_id}"
            )

        if requires_confirmation:
            lines.append(
                "Wymagana jest akceptacja "
                "przed wykonaniem zmian."
            )

        if isinstance(
            blocking_reasons,
            list,
        ) and blocking_reasons:
            lines.append(
                "Blokady: "
                + "; ".join(
                    str(reason)
                    for reason in blocking_reasons
                )
            )

        return "\n".join(lines)

    def _format_research_response(
        self,
        response: dict,
    ) -> str:

        if not isinstance(
            response,
            dict,
        ):
            return str(
                response
            )

        report = response.get(
            "report",
            "",
        )

        if report:
            return str(
                report
            )

        success = response.get(
            "success",
            False,
        )

        if success:
            return (
                "Research Agent zakończył "
                "analizę projektu."
            )

        error = response.get(
            "error",
            "",
        )

        if error:
            return (
                "Research Agent nie zakończył "
                f"analizy: {error}"
            )

        return (
            "Research Agent nie zwrócił raportu."
        )

    def _remember_execution(
        self,
        command: str,
        result,
    ) -> None:

        result_text = str(
            result
        )

        self.memory.add_history(
            command,
            result_text,
        )

        self.cognitive.after_execute(
            command,
            result_text,
        )
