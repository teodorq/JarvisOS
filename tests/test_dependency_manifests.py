from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]


def _requirements(filename: str) -> dict[str, Requirement]:
    result: dict[str, Requirement] = {}
    for raw_line in (ROOT / filename).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        result[canonicalize_name(requirement.name)] = requirement
    return result


def test_lock_contains_every_runtime_dependency() -> None:
    runtime = _requirements("requirements.txt")
    locked = _requirements("requirements-lock.txt")

    assert runtime.keys() <= locked.keys()


def test_slim_runtime_lock_contains_every_runtime_dependency() -> None:
    runtime = _requirements("requirements.txt")
    locked = _requirements("requirements-runtime-lock.txt")

    assert runtime.keys() <= locked.keys()
    excluded = {
        "pytest",
        "openai",
        "google-api-python-client",
        "google-auth-oauthlib",
        "customtkinter",
    }
    assert excluded.isdisjoint(locked)


def test_slim_runtime_lock_is_a_complete_dependency_closure() -> None:
    locked = _requirements("requirements-runtime-lock.txt")

    for name, pinned in locked.items():
        try:
            package = distribution(pinned.name)
        except PackageNotFoundError:
            continue
        for raw_dependency in package.requires or ():
            dependency = Requirement(raw_dependency)
            if dependency.marker is not None and not dependency.marker.evaluate():
                continue
            assert canonicalize_name(dependency.name) in locked, (
                f"{name} wymaga brakującego pakietu {dependency.name}"
            )


def test_lock_contains_supported_optional_integrations() -> None:
    locked = _requirements("requirements-lock.txt")

    for filename in (
        "requirements_google_workspace.txt",
        "requirements_trading_mt5.txt",
    ):
        optional = _requirements(filename)
        assert optional.keys() <= locked.keys()


def test_metatrader_is_pinned_and_windows_only_everywhere() -> None:
    expected_specifier = "==5.0.5735"
    expected_marker = 'sys_platform == "win32"'

    for filename in (
        "requirements.txt",
        "requirements-lock.txt",
        "requirements_trading_mt5.txt",
    ):
        metatrader = _requirements(filename)["metatrader5"]
        assert str(metatrader.specifier) == expected_specifier
        assert str(metatrader.marker) == expected_marker


def test_installer_does_not_retain_download_cache() -> None:
    installer = (ROOT / "install.bat").read_text(encoding="utf-8")

    install_lines = [
        line
        for line in installer.splitlines()
        if " -m pip install " in line
    ]
    assert install_lines
    assert all("--no-cache-dir" in line for line in install_lines)


def test_installer_defaults_to_slim_runtime_and_keeps_dev_mode() -> None:
    installer = (ROOT / "install.bat").read_text(encoding="utf-8")

    assert 'set "REQUIREMENTS=requirements-runtime-lock.txt"' in installer
    assert 'if /I "%~1"=="dev"' in installer
    assert 'set "REQUIREMENTS=requirements-lock.txt"' in installer
