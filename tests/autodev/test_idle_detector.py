import unittest

from app.autodev.idle_detector import IdleDetector


class TestIdleDetector(unittest.TestCase):

    def test_provider_is_used(self) -> None:
        detector = IdleDetector(
            provider=lambda: 123.0
        )

        self.assertEqual(
            detector.idle_seconds(),
            123.0,
        )
        self.assertTrue(
            detector.is_idle(120.0)
        )


if __name__ == "__main__":
    unittest.main()
