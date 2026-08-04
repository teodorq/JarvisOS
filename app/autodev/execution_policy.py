from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
import os
from pathlib import Path
import stat
from typing import Any, Iterable

from app.core.project_paths import resolve_project_root


DEFAULT_PROTECTED_PATHS = (
    ".git",
    ".env",
    "AI_PLIKI",
    "archive",
    "data/autodev/backups",
    "data/autodev/safe_patch_backups",
)

DEFAULT_PROTECTED_FILENAMES = (
    "credentials.json",
    "secrets.json",
)

DEFAULT_PROTECTED_SUFFIXES = (
    ".key",
    ".pem",
    ".p12",
    ".pfx",
)


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    project_root: str | Path | None = None
    max_risk_score: float = 65.0
    max_auto_approval_risk: float = 20.0
    allow_auto_approval: bool = True
    require_validation: bool = True
    reject_symlinks: bool = True
    allowed_extensions: tuple[str, ...] = (
        ".py",
    )
    protected_paths: tuple[str, ...] = (
        DEFAULT_PROTECTED_PATHS
    )
    protected_filenames: tuple[str, ...] = (
        DEFAULT_PROTECTED_FILENAMES
    )
    protected_suffixes: tuple[str, ...] = (
        DEFAULT_PROTECTED_SUFFIXES
    )

    def __post_init__(self) -> None:
        root = resolve_project_root(
            self.project_root
        )
        object.__setattr__(
            self,
            "project_root",
            str(root),
        )

        max_risk = float(
            self.max_risk_score
        )
        auto_risk = float(
            self.max_auto_approval_risk
        )

        if (
            not math.isfinite(max_risk)
            or max_risk < 0.0
        ):
            raise ValueError(
                "max_risk_score musi być skończoną "
                "wartością nieujemną."
            )

        if (
            not math.isfinite(auto_risk)
            or auto_risk < 0.0
            or auto_risk > max_risk
        ):
            raise ValueError(
                "max_auto_approval_risk musi mieścić się "
                "w zakresie 0..max_risk_score."
            )

        extensions = tuple(
            self._normalize_extension(value)
            for value in self.allowed_extensions
            if str(value).strip()
        )
        object.__setattr__(
            self,
            "allowed_extensions",
            extensions,
        )

        object.__setattr__(
            self,
            "protected_paths",
            tuple(
                self._normalize_relative(value)
                for value in self.protected_paths
                if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "protected_filenames",
            tuple(
                str(value).strip().casefold()
                for value in self.protected_filenames
                if str(value).strip()
            ),
        )
        object.__setattr__(
            self,
            "protected_suffixes",
            tuple(
                self._normalize_extension(value)
                for value in self.protected_suffixes
                if str(value).strip()
            ),
        )

    @property
    def root(self) -> Path:
        return Path(
            str(self.project_root)
        ).expanduser().resolve(
            strict=False
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _normalize_extension(
        value: str,
    ) -> str:
        normalized = str(value).strip().casefold()

        if not normalized:
            return ""

        if not normalized.startswith("."):
            normalized = f".{normalized}"

        return normalized

    @staticmethod
    def _normalize_relative(
        value: str,
    ) -> str:
        return str(value).replace(
            "\\",
            "/",
        ).strip("/").casefold()


class ProjectBoundaryPolicy:
    """Validates project-local targets before any write."""

    def __init__(
        self,
        policy: ExecutionPolicy,
    ) -> None:
        self.policy = policy
        self.root = policy.root

    def resolve_target(
        self,
        value: str | Path,
        *,
        require_file: bool = False,
        allow_missing: bool = True,
    ) -> Path:
        raw = str(value).strip()

        if not raw:
            raise ValueError(
                "Brak ścieżki targetu."
            )

        candidate = Path(raw).expanduser()

        if not candidate.is_absolute():
            candidate = self.root / candidate

        resolved = candidate.resolve(
            strict=False
        )

        self._ensure_inside_project(
            resolved
        )

        if resolved == self.root:
            raise ValueError(
                "Nie można modyfikować katalogu głównego projektu."
            )

        relative = resolved.relative_to(
            self.root
        )

        self._ensure_not_protected(
            relative
        )

        if self.policy.reject_symlinks:
            self._ensure_no_symlink_components(
                candidate
            )

        suffix = resolved.suffix.casefold()

        if (
            self.policy.allowed_extensions
            and suffix
            not in self.policy.allowed_extensions
        ):
            raise ValueError(
                "Niedozwolone rozszerzenie pliku: "
                f"{suffix or '<brak>'}."
            )

        if not allow_missing and not resolved.exists():
            raise FileNotFoundError(
                f"Target nie istnieje: {resolved}"
            )

        if require_file and resolved.exists():
            if not resolved.is_file():
                raise ValueError(
                    "Target nie jest zwykłym plikiem."
                )

        return resolved

    def validate_targets(
        self,
        values: Iterable[str | Path],
        *,
        require_file: bool = False,
        allow_missing: bool = True,
    ) -> tuple[list[Path], list[str]]:
        resolved: list[Path] = []
        errors: list[str] = []

        for value in values:
            try:
                path = self.resolve_target(
                    value,
                    require_file=require_file,
                    allow_missing=allow_missing,
                )
            except Exception as error:
                errors.append(
                    f"{value}: {error}"
                )
                continue

            if path not in resolved:
                resolved.append(path)

        if not resolved and not errors:
            errors.append(
                "Brak targetów do walidacji."
            )

        return resolved, errors

    def _ensure_inside_project(
        self,
        resolved: Path,
    ) -> None:
        try:
            resolved.relative_to(
                self.root
            )
        except ValueError as error:
            raise ValueError(
                "Target znajduje się poza projektem."
            ) from error

    def _ensure_not_protected(
        self,
        relative: Path,
    ) -> None:
        normalized = relative.as_posix().casefold()
        filename = relative.name.casefold()
        suffix = relative.suffix.casefold()

        if (
            filename.startswith(".env")
            or filename
            in self.policy.protected_filenames
            or suffix
            in self.policy.protected_suffixes
        ):
            raise ValueError(
                "Target jest chronionym plikiem."
            )

        for protected in self.policy.protected_paths:
            if (
                normalized == protected
                or normalized.startswith(
                    protected + "/"
                )
            ):
                raise ValueError(
                    "Target znajduje się w chronionym "
                    "obszarze projektu."
                )

    def _ensure_no_symlink_components(
        self,
        candidate: Path,
    ) -> None:
        absolute = candidate

        if not absolute.is_absolute():
            absolute = self.root / absolute

        try:
            relative = absolute.relative_to(
                self.root
            )
        except ValueError:
            relative = absolute.resolve(
                strict=False
            ).relative_to(
                self.root
            )

        current = self.root

        for part in relative.parts:
            current = current / part

            if self._is_link_or_reparse_point(
                current
            ):
                raise ValueError(
                    "Target zawiera dowiązanie symboliczne."
                )

        lexical = os.path.normcase(
            os.path.abspath(
                os.path.normpath(
                    str(absolute)
                )
            )
        )
        resolved = os.path.normcase(
            str(
                absolute.resolve(
                    strict=False
                )
            )
        )

        if lexical != resolved:
            raise ValueError(
                "Target zawiera dowiązanie symboliczne."
            )

    @staticmethod
    def _is_link_or_reparse_point(
        path: Path,
    ) -> bool:
        try:
            metadata = os.lstat(path)
        except OSError:
            return False

        if stat.S_ISLNK(metadata.st_mode):
            return True

        reparse_flag = getattr(
            stat,
            "FILE_ATTRIBUTE_REPARSE_POINT",
            0x400,
        )
        file_attributes = getattr(
            metadata,
            "st_file_attributes",
            0,
        )
        return bool(
            file_attributes & reparse_flag
        )


def parse_risk_score(
    value: Any,
) -> float:
    try:
        result = float(
            value or 0.0
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "Nieprawidłowy risk_score."
        ) from error

    if not math.isfinite(result):
        raise ValueError(
            "risk_score musi być wartością skończoną."
        )

    if result < 0.0:
        raise ValueError(
            "risk_score nie może być ujemny."
        )

    return result
