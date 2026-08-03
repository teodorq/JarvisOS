from __future__ import annotations

import unittest

from app.ai.software_engineer import (
    FeatureDependencyPlanner,
    FeatureFileSpec,
    FeaturePlanner,
)


class FeaturePlannerTests(unittest.TestCase):

    def test_builds_multi_file_feature_blueprint(self) -> None:
        plan = FeaturePlanner().plan(
            "Dodaj system powiadomień",
            feature_name="NotificationCenter",
        )

        self.assertEqual(
            plan.feature_name,
            "NotificationCenter",
        )
        self.assertGreaterEqual(
            len(plan.files),
            5,
        )
        self.assertIn(
            "app/features/notification_center/service.py",
            plan.rollback_scope,
        )
        self.assertTrue(
            plan.validation_targets
        )

    def test_creation_order_respects_dependencies(self) -> None:
        plan = FeaturePlanner().plan(
            "Dodaj raportowanie",
            feature_name="ReportEngine",
        )

        positions = {
            file_id: index
            for index, file_id
            in enumerate(
                plan.creation_order
            )
        }

        self.assertLess(
            positions["models"],
            positions["service"],
        )
        self.assertLess(
            positions["service"],
            positions["controller"],
        )
        self.assertLess(
            positions["controller"],
            positions["package_init"],
        )
        self.assertLess(
            positions["package_init"],
            positions["tests"],
        )

    def test_optional_repository_is_added(self) -> None:
        plan = FeaturePlanner().plan(
            "Dodaj historię zdarzeń",
            feature_name="EventHistory",
            include_repository=True,
        )
        file_map = plan.file_map()

        self.assertIn(
            "repository",
            file_map,
        )
        self.assertIn(
            "repository",
            file_map["service"].dependencies,
        )

    def test_controller_can_be_disabled(self) -> None:
        plan = FeaturePlanner().plan(
            "Dodaj analizę danych",
            feature_name="DataAnalysis",
            include_controller=False,
        )

        self.assertNotIn(
            "controller",
            plan.file_map(),
        )

    def test_custom_safe_package_path_is_supported(self) -> None:
        plan = FeaturePlanner().plan(
            "Dodaj moduł cen",
            feature_name="PriceEngine",
            package_path="app/ai/price_engine",
        )

        self.assertEqual(
            plan.package_path,
            "app/ai/price_engine",
        )
        self.assertTrue(
            all(
                item.relative_path.startswith(
                    "app/ai/price_engine/"
                )
                or item.category == "test"
                for item in plan.files
            )
        )

    def test_unsafe_package_path_is_rejected(self) -> None:
        with self.assertRaises(
            ValueError
        ):
            FeaturePlanner().plan(
                "Dodaj moduł",
                feature_name="UnsafeFeature",
                package_path="../outside",
            )

    def test_duplicate_paths_are_rejected(self) -> None:
        files = [
            FeatureFileSpec(
                file_id="one",
                relative_path="app/x.py",
                purpose="one",
                category="service",
            ),
            FeatureFileSpec(
                file_id="two",
                relative_path="app/x.py",
                purpose="two",
                category="service",
            ),
        ]

        with self.assertRaises(
            ValueError
        ):
            FeatureDependencyPlanner().validate(
                files
            )

    def test_blueprint_serializes_to_dictionary(self) -> None:
        plan = FeaturePlanner().plan(
            "Dodaj eksport danych",
            feature_name="DataExport",
        )

        data = plan.to_dict()

        self.assertEqual(
            data["feature_slug"],
            "data_export",
        )
        self.assertTrue(
            data["metadata"]["multi_file"]
        )
        self.assertGreater(
            data["estimated_roi"],
            0.0,
        )
        self.assertLessEqual(
            data["estimated_risk"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
