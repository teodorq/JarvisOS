from __future__ import annotations
import ast
from pathlib import Path
import unittest
from app.ai.software_engineer.business_commercial_router import BusinessCommercialRouter
from app.gui.command_safety import is_read_only_learning_command
class B89B95RoutingGuiTests(unittest.TestCase):
    def test_read_and_mutating_classification(self):
        self.assertTrue(is_read_only_learning_command('Pokaż status wydania produkcyjnego'))
        self.assertFalse(is_read_only_learning_command('Eksportuj wydanie produkcyjne'))
    def test_router_phrases(self):
        self.assertTrue(BusinessCommercialRouter.can_handle('Status B89-B95'))
        self.assertTrue(BusinessCommercialRouter.can_handle('Zbuduj manifest dystrybucji'))
    def test_gui_page_is_integrated(self):
        source=(Path(__file__).resolve().parents[1]/'app/gui/main_window.py').read_text(encoding='utf-8'); self.assertIn('BusinessCommercialPage',source); self.assertIn('PRODUKCJA I SPRZEDAŻ',source); self.assertLess(len(source.splitlines()),440)
    def test_business_service_exposes_all_stages(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'app/business/business_commercial_service.py').read_text(encoding='utf-8')); names={n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
        for name in ('commercial_platform_status','prepare_production_version','initialize_commercial_license_authority','build_distribution_manifest','export_customer_deployment','export_sales_handoff','export_production_release'): self.assertIn(name,names)
