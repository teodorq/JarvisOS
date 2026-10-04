from __future__ import annotations

import math
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from app.gui.halo_widget import HaloWidget
    from app.gui.orb_frame_budget import OrbFrameBudget
    from app.core.performance_profile import BALANCED, LOW_RESOURCE

    HAS_QT = True
except Exception:
    QApplication = None
    HaloWidget = None
    OrbFrameBudget = None
    LOW_RESOURCE = None
    BALANCED = None
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
class HaloIdlePerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_idle_states_use_a_lighter_frame_rate(self) -> None:
        halo = HaloWidget()
        try:
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001 - focused runtime check
                halo.IDLE_FRAME_INTERVAL_MS,
            )

            halo.set_state("thinking")
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001 - focused runtime check
                halo.ACTIVE_FRAME_INTERVAL_MS,
            )

            halo.set_state("success")
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001 - focused runtime check
                halo.IDLE_FRAME_INTERVAL_MS,
            )
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_orb_animation_crosses_old_loop_boundary_without_reset(self) -> None:
        halo = HaloWidget()
        try:
            halo._angle = 359.9  # noqa: SLF001 - boundary regression check
            halo._pulse = math.tau - 0.001  # noqa: SLF001
            halo._scan = 359.9  # noqa: SLF001 - boundary regression check

            halo._tick()  # noqa: SLF001 - drive exactly one animation frame

            self.assertGreater(halo._angle, 360.0)  # noqa: SLF001
            self.assertGreater(halo._pulse, math.tau)  # noqa: SLF001
            self.assertGreater(halo._scan, 360.0)  # noqa: SLF001
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_cinematic_orb_contains_ten_thousand_particles(self) -> None:
        halo = HaloWidget()
        try:
            self.assertEqual(halo._renderer.PARTICLE_COUNT, 10_000)  # noqa: SLF001
            self.assertEqual(len(halo._renderer._particles), 10_000)  # noqa: SLF001
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_idle_orb_reuses_particle_geometry_every_other_frame(self) -> None:
        halo = HaloWidget()
        try:
            renderer = halo._renderer  # noqa: SLF001 - focused render regression
            renderer._particle_cache = None  # noqa: SLF001
            renderer._particle_geometry_builds = 0  # noqa: SLF001
            halo.resize(640, 640)
            halo.show()
            halo.repaint()
            self.app.processEvents()
            first = renderer._particle_geometry_builds  # noqa: SLF001

            halo._tick()  # noqa: SLF001 - advance continuous outer animation
            halo.repaint()
            self.app.processEvents()
            self.assertEqual(renderer._particle_geometry_builds, first)  # noqa: SLF001

            halo._tick()  # noqa: SLF001
            halo.repaint()
            self.app.processEvents()
            self.assertEqual(renderer._particle_geometry_builds, first + 1)  # noqa: SLF001
        finally:
            halo.set_animation_active(False)
            halo.hide()
            halo.deleteLater()

    def test_orb_reduces_detail_only_after_repeated_slow_frames(self) -> None:
        budget = OrbFrameBudget(degrade_after=3, recover_after=4)

        self.assertEqual(budget.observe(30.0, active=True), 1)
        self.assertEqual(budget.observe(30.0, active=True), 1)
        self.assertEqual(budget.observe(30.0, active=True), 2)

    def test_orb_restores_detail_only_after_sustained_fast_frames(self) -> None:
        budget = OrbFrameBudget(degrade_after=1, recover_after=3)
        self.assertEqual(budget.observe(30.0, active=True), 2)

        self.assertEqual(budget.observe(5.0, active=True), 2)
        self.assertEqual(budget.observe(5.0, active=True), 2)
        self.assertEqual(budget.observe(5.0, active=True), 1)

    def test_neutral_render_time_does_not_oscillate_quality(self) -> None:
        budget = OrbFrameBudget(degrade_after=1, recover_after=2)
        self.assertEqual(budget.observe(30.0, active=True), 2)

        for _ in range(10):
            self.assertEqual(budget.observe(15.0, active=True), 2)

    def test_renderer_stride_preserves_state_and_size_detail_rules(self) -> None:
        halo = HaloWidget()
        try:
            stride = halo._renderer._particle_stride  # noqa: SLF001
            self.assertEqual(stride(640.0, "thinking", 1), 1)
            self.assertEqual(stride(640.0, "thinking", 2), 2)
            self.assertEqual(stride(640.0, "idle", 1), 2)
            self.assertEqual(stride(150.0, "thinking", 3), 9)
            self.assertEqual(stride(640.0, "thinking", 99), 3)
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_low_resource_profile_starts_with_lighter_rendering(self) -> None:
        halo = HaloWidget(performance_profile=LOW_RESOURCE)
        try:
            self.assertEqual(halo.particle_stride_multiplier, 2)
            self.assertEqual(halo._timer.interval(), 80)  # noqa: SLF001
            halo.set_state("thinking")
            self.assertEqual(halo._timer.interval(), 50)  # noqa: SLF001
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_profile_can_switch_to_low_resource_without_restart(self) -> None:
        halo = HaloWidget(performance_profile=BALANCED)
        try:
            halo.set_performance_profile(LOW_RESOURCE)
            self.assertEqual(halo.performance_profile.name, "low_resource")
            self.assertEqual(halo.particle_stride_multiplier, 2)
            self.assertEqual(
                halo._timer.interval(),  # noqa: SLF001
                LOW_RESOURCE.idle_frame_interval_ms,
            )
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_slow_frames_reduce_refresh_rate_and_fast_frames_restore_it(self) -> None:
        halo = HaloWidget()
        try:
            halo.set_state("thinking")
            for _ in range(3):
                halo._frame_budget.observe(30.0, active=True)  # noqa: SLF001
            halo._timer.setInterval(halo._frame_interval_ms())  # noqa: SLF001
            self.assertEqual(halo.particle_stride_multiplier, 2)
            self.assertEqual(halo._timer.interval(), 43)  # noqa: SLF001

            for _ in range(90):
                halo._frame_budget.observe(5.0, active=True)  # noqa: SLF001
            halo._timer.setInterval(halo._frame_interval_ms())  # noqa: SLF001
            self.assertEqual(halo.particle_stride_multiplier, 1)
            self.assertEqual(halo._timer.interval(), 33)  # noqa: SLF001
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()

    def test_adaptive_interval_preserves_time_based_motion_speed(self) -> None:
        halo = HaloWidget()
        try:
            halo.set_state("thinking")
            halo._angle = 0.0  # noqa: SLF001
            halo._last_tick_at = 10.0  # noqa: SLF001
            halo._timer.setInterval(43)  # noqa: SLF001

            with patch("app.gui.halo_widget.perf_counter", return_value=10.043):
                halo._tick()  # noqa: SLF001

            expected = halo.SPEEDS["thinking"] * 43 / 33
            self.assertAlmostEqual(halo._angle, expected, places=5)  # noqa: SLF001
        finally:
            halo.set_animation_active(False)
            halo.deleteLater()


if __name__ == "__main__":
    unittest.main()
