from __future__ import annotations
from app.ai.llm import LocalLLM

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


class PatchModel(Protocol):
    def generate_patch(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class LLMPatchRequest:
    goal: str
    path: str
    issue_type: str
    strategy: str
    source_content: str
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LLMPatchResult:
    success: bool
    status: str
    proposed_content: str = ""
    explanation: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMPatchGenerator:
    """
    Bezpieczna warstwa abstrakcji dla modelu generującego kod.

    Sama klasa nie łączy się z internetem ani z API.
    Model jest wstrzykiwany przez interfejs PatchModel.
    """

    def __init__(
        self,
        model: PatchModel | None = None,
        max_source_chars: int = 200_000,
    ) -> None:

        self.model = model or LocalLLM()
        self.max_source_chars = max_source_chars
        self.last_result: LLMPatchResult | None = None

    def generate(
        self,
        request: LLMPatchRequest,
    ) -> LLMPatchResult:

        if not isinstance(
            request,
            LLMPatchRequest,
        ):
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="INVALID_REQUEST",
                    errors=[
                        "Wymagany jest LLMPatchRequest."
                    ],
                )
            )

        if not request.path.strip():
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="MISSING_PATH",
                    errors=[
                        "Brak ścieżki pliku."
                    ],
                )
            )

        if not request.source_content:
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="MISSING_SOURCE",
                    errors=[
                        "Brak kodu źródłowego."
                    ],
                )
            )

        if len(
            request.source_content
        ) > self.max_source_chars:
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="SOURCE_TOO_LARGE",
                    errors=[
                        "Kod źródłowy przekracza limit."
                    ],
                )
            )

        if self.model is None:
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="MODEL_UNAVAILABLE",
                    errors=[
                        (
                            "Nie skonfigurowano modelu "
                            "generującego patch."
                        )
                    ],
                )
            )

        try:
            raw = self.model.generate_patch(
                request.to_dict()
            )
        except Exception as error:
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="MODEL_ERROR",
                    errors=[
                        (
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    ],
                )
            )

        if not isinstance(
            raw,
            dict,
        ):
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="INVALID_MODEL_RESPONSE",
                    errors=[
                        "Model zwrócił niepoprawny format."
                    ],
                )
            )

        proposed_content = str(
            raw.get(
                "proposed_content",
                "",
            )
        )

        if not proposed_content:
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="EMPTY_PROPOSAL",
                    errors=[
                        "Model nie zwrócił kodu."
                    ],
                    raw_response=dict(raw),
                )
            )

        if proposed_content == request.source_content:
            return self._finish(
                LLMPatchResult(
                    success=False,
                    status="NO_CHANGE",
                    errors=[
                        "Model nie zaproponował zmiany."
                    ],
                    raw_response=dict(raw),
                )
            )

        result = LLMPatchResult(
            success=True,
            status="PROPOSAL_READY",
            proposed_content=proposed_content,
            explanation=str(
                raw.get(
                    "explanation",
                    "",
                )
            ),
            warnings=[
                str(item)
                for item in raw.get(
                    "warnings",
                    [],
                )
                if str(item).strip()
            ],
            raw_response=dict(raw),
        )

        return self._finish(
            result
        )

    def _finish(
        self,
        result: LLMPatchResult,
    ) -> LLMPatchResult:

        self.last_result = result
        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "model_available": self.model is not None,
            "max_source_chars": self.max_source_chars,
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
