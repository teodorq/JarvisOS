from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from typing import Any, Iterable, Mapping, Sequence


class ProcessPolicyError(ValueError):
    """Raised when a process request violates the execution policy."""


@dataclass(
    frozen=True,
    slots=True,
)
class ProcessResult:
    command: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    truncated: bool = False
    pid: int | None = None

    @property
    def success(self) -> bool:
        return (
            not self.timed_out
            and self.returncode == 0
        )

    def as_dict(self) -> dict:
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_seconds": self.duration_seconds,
            "truncated": self.truncated,
            "pid": self.pid,
        }


class SafeProcessRunner:
    """Runs allow-listed processes without a command shell."""

    _SENSITIVE_ENV_MARKERS = (
        "API_KEY",
        "ACCESS_KEY",
        "PRIVATE_KEY",
        "PASSWORD",
        "SECRET",
        "TOKEN",
    )

    def __init__(
        self,
        *,
        project_root: str | Path,
        allowed_executables: Iterable[str | Path] = (),
        max_timeout_seconds: float = 600.0,
        max_output_chars: int = 8000,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.allowed_executables = tuple(
            str(item)
            for item in allowed_executables
            if str(item).strip()
        )
        self.max_timeout_seconds = float(
            max_timeout_seconds
        )
        self.max_output_chars = int(
            max_output_chars
        )

        if self.max_timeout_seconds <= 0:
            raise ValueError(
                "max_timeout_seconds must be greater than 0"
            )

        if self.max_output_chars < 256:
            raise ValueError(
                "max_output_chars must be at least 256"
            )

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        timeout: float,
        allowed_executables: Iterable[str | Path] = (),
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        prepared = self._prepare_command(
            command,
            allowed_executables=allowed_executables,
        )
        working_directory = self._resolve_cwd(
            cwd
        )
        safe_timeout = self._validate_timeout(
            timeout
        )
        safe_env = self._safe_environment(
            env
        )

        started = time.monotonic()
        process: subprocess.Popen[bytes] | None = None
        timed_out = False

        with (
            tempfile.TemporaryFile() as stdout_file,
            tempfile.TemporaryFile() as stderr_file,
        ):
            try:
                process = subprocess.Popen(
                    list(prepared),
                    cwd=str(
                        working_directory
                    ),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    shell=False,
                    env=safe_env,
                    close_fds=True,
                    **self._process_group_options(),
                )

                try:
                    process.wait(
                        timeout=safe_timeout
                    )
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self._terminate_process(
                        process
                    )

                stdout, stdout_truncated = (
                    self._read_limited(
                        stdout_file
                    )
                )
                stderr, stderr_truncated = (
                    self._read_limited(
                        stderr_file
                    )
                )

            except OSError as error:
                duration = (
                    time.monotonic()
                    - started
                )
                return ProcessResult(
                    command=prepared,
                    returncode=None,
                    stdout="",
                    stderr=(
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                    timed_out=False,
                    duration_seconds=duration,
                    pid=(
                        process.pid
                        if process is not None
                        else None
                    ),
                )

        duration = time.monotonic() - started

        return ProcessResult(
            command=prepared,
            returncode=(
                process.returncode
                if process is not None
                else None
            ),
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_seconds=duration,
            truncated=(
                stdout_truncated
                or stderr_truncated
            ),
            pid=(
                process.pid
                if process is not None
                else None
            ),
        )

    def open(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        allowed_executables: Iterable[str | Path] = (),
        env: Mapping[str, str] | None = None,
        **popen_options: Any,
    ) -> subprocess.Popen:
        """Open a managed process when a caller needs a live protocol."""
        forbidden = {"shell", "cwd", "env", "close_fds"} & popen_options.keys()
        if forbidden:
            raise ProcessPolicyError(
                "Managed process options cannot override safety controls."
            )
        prepared = self._prepare_command(
            command,
            allowed_executables=allowed_executables,
        )
        working_directory = self._resolve_cwd(cwd)
        group_options = self._process_group_options()
        extra_flags = int(popen_options.pop("creationflags", 0) or 0)
        if os.name == "nt":
            group_options["creationflags"] = (
                int(group_options.get("creationflags", 0)) | extra_flags
            )
        return subprocess.Popen(
            list(prepared),
            cwd=str(working_directory),
            shell=False,
            env=self._safe_environment(env),
            close_fds=True,
            **group_options,
            **popen_options,
        )

    def spawn(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        allowed_executables: Iterable[str | Path] = (),
        env: Mapping[str, str] | None = None,
    ) -> int:
        prepared = self._prepare_command(
            command,
            allowed_executables=allowed_executables,
        )
        working_directory = self._resolve_cwd(
            cwd
        )

        process = subprocess.Popen(
            list(prepared),
            cwd=str(
                working_directory
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            env=self._safe_environment(
                env
            ),
            close_fds=True,
            **self._process_group_options(),
        )

        return int(
            process.pid
        )

    def _prepare_command(
        self,
        command: Sequence[str],
        *,
        allowed_executables: Iterable[str | Path],
    ) -> tuple[str, ...]:
        if isinstance(
            command,
            (str, bytes),
        ):
            raise ProcessPolicyError(
                "Command must be a sequence of arguments, not a shell string."
            )

        values = tuple(
            str(item)
            for item in command
        )

        if not values:
            raise ProcessPolicyError(
                "Command cannot be empty."
            )

        if len(values) > 64:
            raise ProcessPolicyError(
                "Command contains too many arguments."
            )

        if any(
            not value
            or "\x00" in value
            for value in values
        ):
            raise ProcessPolicyError(
                "Command contains an empty or invalid argument."
            )

        if sum(
            len(value)
            for value in values
        ) > 32768:
            raise ProcessPolicyError(
                "Command is too long."
            )

        allowed = (
            *self.allowed_executables,
            *tuple(
                str(item)
                for item in allowed_executables
            ),
        )

        if not self._is_allowed_executable(
            values[0],
            allowed,
        ):
            raise ProcessPolicyError(
                "Executable is not allowed by process policy."
            )

        return values

    def _is_allowed_executable(
        self,
        executable: str,
        allowed: Sequence[str],
    ) -> bool:
        if not allowed:
            return False

        executable_path = Path(
            executable
        ).expanduser()
        executable_name = (
            executable_path.name.casefold()
        )
        executable_absolute = str(
            executable_path.resolve(
                strict=False
            )
        ).casefold()

        for candidate in allowed:
            candidate_path = Path(
                candidate
            ).expanduser()

            if candidate_path.is_absolute():
                if str(
                    candidate_path.resolve(
                        strict=False
                    )
                ).casefold() == executable_absolute:
                    return True

                continue

            if (
                candidate_path.name.casefold()
                == executable_name
            ):
                return True

        return False

    def _resolve_cwd(
        self,
        value: str | Path | None,
    ) -> Path:
        candidate = Path(
            value
            if value is not None
            else self.project_root
        ).expanduser().resolve(
            strict=False
        )

        try:
            candidate.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ProcessPolicyError(
                "Process working directory is outside the project."
            ) from error

        if not candidate.is_dir():
            raise ProcessPolicyError(
                "Process working directory does not exist."
            )

        return candidate

    def _validate_timeout(
        self,
        value: float,
    ) -> float:
        try:
            timeout = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise ProcessPolicyError(
                "Timeout must be a number."
            ) from error

        if (
            timeout <= 0
            or timeout
            > self.max_timeout_seconds
        ):
            raise ProcessPolicyError(
                "Timeout is outside the allowed range."
            )

        return timeout

    def _safe_environment(
        self,
        provided: Mapping[str, str] | None,
    ) -> dict[str, str]:
        source = dict(
            os.environ
            if provided is None
            else provided
        )
        result: dict[str, str] = {}

        for key, value in source.items():
            upper = str(
                key
            ).upper()

            if any(
                marker in upper
                for marker
                in self._SENSITIVE_ENV_MARKERS
            ):
                continue

            result[
                str(key)
            ] = str(value)

        return result

    def _read_limited(
        self,
        file_object,
    ) -> tuple[str, bool]:
        file_object.seek(0)
        limit = self.max_output_chars
        data = file_object.read(
            limit + 1
        )
        truncated = len(data) > limit
        data = data[:limit]

        return (
            data.decode(
                "utf-8",
                errors="replace",
            ),
            truncated,
        )

    @staticmethod
    def _process_group_options(
    ) -> dict:
        if os.name == "nt":
            return {
                "creationflags": (
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                ),
            }

        return {
            "start_new_session": True,
        }

    @staticmethod
    def _terminate_process(
        process: subprocess.Popen,
    ) -> None:
        if process.poll() is not None:
            return

        try:
            if os.name != "nt":
                os.killpg(
                    process.pid,
                    signal.SIGTERM,
                )
            else:
                process.terminate()

            process.wait(
                timeout=1.0
            )
            return

        except (
            OSError,
            ProcessLookupError,
            subprocess.TimeoutExpired,
        ):
            raise RuntimeError("AutoDev: przechwycony wyjątek")

        try:
            if os.name != "nt":
                os.killpg(
                    process.pid,
                    signal.SIGKILL,
                )
            else:
                process.kill()

            process.wait(
                timeout=1.0
            )
        except (
            OSError,
            ProcessLookupError,
            subprocess.TimeoutExpired,
        ):
            raise RuntimeError("AutoDev: przechwycony wyjątek")
