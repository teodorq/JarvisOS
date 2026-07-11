from dataclasses import dataclass


@dataclass
class AutoDevReport:

    context: object

    def build(self):

        lines = [
            "AUTODEV REPORT",
            ""
        ]

        lines.append(
            self.context.summary()
        )

        if self.context.reasoning:

            lines.append("")
            lines.append(
                self.context.reasoning.report()
            )

        if self.context.development_plan:

            lines.append("")
            lines.append(
                self.context.development_plan.summary()
            )

        if self.context.workflow_result:

            lines.append("")
            lines.append(
                self.context.workflow_result.summary()
            )

        return "\n".join(lines)