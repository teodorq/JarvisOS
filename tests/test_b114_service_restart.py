from tempfile import TemporaryDirectory
import unittest

from app.stability.service_restart import SafeServiceRestartCenter


class B114ServiceRestartTests(unittest.TestCase):
    def test_restart_restores_checkpoint_exactly(self) -> None:
        with TemporaryDirectory() as temporary:
            value = {"generation": 1, "mode": "READY"}
            center = SafeServiceRestartCenter(temporary)
            center.register(
                "demo",
                lambda: dict(value),
                lambda: value.update({"generation": 2, "mode": "RESTARTING"}),
                lambda checkpoint: (value.clear(), value.update(checkpoint)),
            )
            plan = center.prepare("demo")
            self.assertEqual(plan["status"], "PREPARED")
            result = center.execute(plan["plan_id"])
            self.assertTrue(result["state_restored"])
            self.assertEqual(value, {"generation": 1, "mode": "READY"})

    def test_execute_requires_prepared_plan(self) -> None:
        with TemporaryDirectory() as temporary:
            center = SafeServiceRestartCenter(temporary)
            with self.assertRaisesRegex(ValueError, "brak przygotowanego"):
                center.execute()

    def test_unknown_service_is_blocked(self) -> None:
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "nie jest zarejestrowana"):
                SafeServiceRestartCenter(temporary).prepare("unknown")


if __name__ == "__main__":
    unittest.main()
