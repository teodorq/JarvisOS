from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from app.vision.moondream import MoondreamVision


def test_moondream_reports_missing_image_without_network_call() -> None:
    with TemporaryDirectory() as directory:
        missing = Path(directory) / "missing.webp"

        result = MoondreamVision().analyze(str(missing))

    assert "Nie znaleziono obrazu" in result


def test_qwen_optimization_stays_in_memory() -> None:
    from app.vision.qwen_vision import QwenVision

    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "screen.webp"
        Image.new("RGB", (1200, 600), color=(12, 36, 60)).save(
            source, format="WEBP"
        )

        encoded = QwenVision._encode_optimized_image(str(source))

        assert encoded
        assert sorted(path.name for path in root.iterdir()) == ["screen.webp"]
