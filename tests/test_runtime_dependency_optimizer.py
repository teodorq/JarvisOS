from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from tools.optimize_runtime_dependencies import optimize_runtime_dependencies


def _file(path: Path, size: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_optimizer_keeps_jarvis_google_apis_and_windows_flac() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary) / "site-packages"
        documents = root / "googleapiclient/discovery_cache/documents"
        for name in (
            "calendar.v3.json",
            "drive.v3.json",
            "gmail.v1.json",
            "compute.v1.json",
        ):
            _file(documents / name)
        speech = root / "speech_recognition"
        _file(speech / "flac-win32.exe")
        _file(speech / "flac-linux-x86_64")
        _file(speech / "pocketsphinx-data/en-US/model.bin", 100)

        preview = optimize_runtime_dependencies(root)
        result = optimize_runtime_dependencies(root, apply=True)

        assert preview["candidate_count"] == 3
        assert result["reclaimed_bytes"] == 120
        assert (documents / "calendar.v3.json").exists()
        assert (documents / "drive.v3.json").exists()
        assert (documents / "gmail.v1.json").exists()
        assert not (documents / "compute.v1.json").exists()
        assert (speech / "flac-win32.exe").exists()
        assert not (speech / "flac-linux-x86_64").exists()
        assert not (speech / "pocketsphinx-data").exists()


def test_optimizer_rejects_an_unscoped_directory() -> None:
    with TemporaryDirectory() as temporary:
        with pytest.raises(ValueError):
            optimize_runtime_dependencies(temporary, apply=True)


def test_windows_installers_apply_runtime_optimization() -> None:
    root = Path(__file__).resolve().parents[1]
    batch = (root / "install.bat").read_text(encoding="utf-8")
    business = (
        root / "app" / "business" / "installation_scripts.py"
    ).read_text(encoding="utf-8")

    assert "optimize_runtime_dependencies.py" in batch
    assert "optimize_runtime_dependencies.py" in business
    assert "--apply" in batch
    assert "--apply" in business
