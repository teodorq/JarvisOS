import unittest
from unittest.mock import MagicMock

from app.ai.meta_executive.meta_controller import MetaController
from app.ai.meta_executive.meta_engine import MetaEngine
from app.ai.meta_executive.meta_memory import MetaMemory
from app.ai.meta_executive.meta_planner import MetaPlanner
from app.ai.meta_executive.meta_state import MetaState


class TestMetaExecutive(unittest.TestCase):

    def test_state(self):
        s = MetaState(objective="Rozwijaj cały system")
        self.assertTrue(s.meta_id.startswith("meta-"))
        self.assertEqual(s.status, "CREATED")

    def test_memory(self):
        m = MetaMemory()
        s = MetaState(objective="Test")
        m.remember(s)
        self.assertEqual(m.summary()["total_records"], 1)

    def test_planner(self):
        p = MetaPlanner()
        plan = p.build_plan("zarządzaj całym systemem")
        self.assertTrue(plan["can_execute"])
        self.assertTrue(plan["selected_layer"])

    def test_engine(self):
        engine = MetaEngine(
            executive_controller=MagicMock(
                handle=MagicMock(return_value={"success": True, "status": "COMPLETED"})
            )
        )
        created = engine.create_session("zarządzaj całym systemem")
        self.assertTrue(created["success"])

    def test_controller_summary(self):
        c = MetaController()
        r = c.handle("meta executive summary")
        self.assertTrue(r["success"])

    def test_can_handle(self):
        c = MetaController()
        self.assertTrue(c.can_handle("meta executive start test"))
        self.assertFalse(c.can_handle("otwórz youtube"))

    def test_find_similar(self):
        m = MetaMemory()
        m.remember(MetaState(objective="Rozwijaj projekt"))
        self.assertEqual(len(m.find_similar_objectives("projekt")),1)

    def test_priority(self):
        p = MetaPlanner()
        plan = p.build_plan("awaria całego systemu")
        self.assertIn(plan["priority"], ["HIGH","CRITICAL"])

    def test_export(self):
        m=MetaMemory()
        m.remember(MetaState(objective="A"))
        self.assertIn("records",m.export_data())

    def test_summary(self):
        e=MetaEngine()
        self.assertIn("total_sessions",e.summary())

if __name__=="__main__":
    unittest.main()
