
from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.autodev.code_refactoring_engine import (
    CodeRefactoringEngine,
)
from app.autodev.developer_reasoning_engine import (
    DeveloperReasoningEngine,
)
from app.autodev.llm_patch_generator import (
    LLMPatchGenerator,
    LLMPatchRequest,
)


@dataclass(slots=True)
class DeveloperAIEnginePolicy:
    project_root: str = default_project_root()
    prefer_local_refactoring: bool = True
    allow_llm_fallback: bool = True
    max_source_chars: int = 200_000


class DeveloperAIEngine:
    """
    Centralny silnik przygotowania propozycji zmian.

    Kolejność:
    1. reasoning,
    2. lokalna bezpieczna refaktoryzacja,
    3. opcjonalny fallback do generatora LLM,
    4. zwrot propozycji bez zapisu do pliku.
    """

    def __init__(
        self,
        policy: DeveloperAIEnginePolicy | None = None,
        reasoning_engine: DeveloperReasoningEngine | None = None,
        refactoring_engine: CodeRefactoringEngine | None = None,
        llm_generator: LLMPatchGenerator | None = None,
    ) -> None:

        self.policy = (
            policy
            or DeveloperAIEnginePolicy()
        )

        self.reasoning_engine = (
            reasoning_engine
            or DeveloperReasoningEngine()
        )

        self.refactoring_engine = (
            refactoring_engine
            or CodeRefactoringEngine(
                project_root=self.policy.project_root
            )
        )

        self.llm_generator = (
            llm_generator
            or LLMPatchGenerator(
                max_source_chars=(
                    self.policy.max_source_chars
                )
            )
        )

        self.last_result: dict[str, Any] | None = None

    def generate(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any]:

        reasoning = self.reasoning_engine.reason(
            plan
        )

        if not reasoning.success:
            return self._finish(
                {
                    "success": False,
                    "status": reasoning.status,
                    "reasoning": reasoning.to_dict(),
                }
            )

        issue = plan.get(
            "issue",
            {},
        )

        if not isinstance(issue, dict):
            issue = {}

        line = self._safe_int(
            plan.get(
                "line",
                issue.get(
                    "line",
                    0,
                ),
            )
        )

        if self.policy.prefer_local_refactoring:
            local_result = (
                self.refactoring_engine.refactor(
                    path=reasoning.path,
                    issue_type=(
                        reasoning.issue_type
                    ),
                    line=line,
                )
            )

            if local_result.success:
                return self._finish(
                    {
                        "success": True,
                        "status": "LOCAL_PROPOSAL_READY",
                        "reasoning": reasoning.to_dict(),
                        "proposal": (
                            local_result.to_dict()
                        ),
                        "source": "local_refactoring",
                    }
                )

            if (
                local_result.status != "NEEDS_LLM"
                or not self.policy.allow_llm_fallback
            ):
                return self._finish(
                    {
                        "success": False,
                        "status": local_result.status,
                        "reasoning": reasoning.to_dict(),
                        "proposal": (
                            local_result.to_dict()
                        ),
                        "source": "local_refactoring",
                    }
                )

        if not self.policy.allow_llm_fallback:
            return self._finish(
                {
                    "success": False,
                    "status": "LLM_FALLBACK_DISABLED",
                    "reasoning": reasoning.to_dict(),
                }
            )

        file_path = Path(
            reasoning.path
        )

        try:
            source_content = file_path.read_text(
                encoding="utf-8"
            )
        except Exception as error:
            return self._finish(
                {
                    "success": False,
                    "status": "READ_FAILED",
                    "reasoning": reasoning.to_dict(),
                    "error": (
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                }
            )

        llm_request = LLMPatchRequest(
            goal=reasoning.goal,
            path=reasoning.path,
            issue_type=reasoning.issue_type,
            strategy=reasoning.strategy,
            source_content=source_content,
            constraints=list(
                reasoning.constraints
            ),
            metadata={
                "risks": list(
                    reasoning.risks
                ),
                "requires_approval": True,
            },
        )

        llm_result = self.llm_generator.generate(
            llm_request
        )

        return self._finish(
            {
                "success": llm_result.success,
                "status": llm_result.status,
                "reasoning": reasoning.to_dict(),
                "proposal": llm_result.to_dict(),
                "source": "llm_patch_generator",
            }
        )

    def _safe_int(
        self,
        value: Any,
    ) -> int:

        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    def _finish(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        self.last_result = dict(
            result
        )

        return dict(
            result
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "policy": asdict(
                self.policy
            ),
            "last_result": self.last_result,
            "reasoning": (
                self.reasoning_engine.status()
            ),
            "refactoring": (
                self.refactoring_engine.status()
            ),
            "llm": (
                self.llm_generator.status()
            ),
        }
