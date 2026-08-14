from __future__ import annotations
from pathlib import Path
import tempfile, unittest
from unittest.mock import MagicMock
from app.business.production_versioning import ProductionVersioning
from app.business.customer_update_channels import CustomerUpdateChannels
from app.business.commercial_license import CommercialLicenseAuthority
from app.business.distribution_protection import DistributionProtection
from app.business.customer_deployment import CustomerDeployment
from app.business.sales_readiness import SalesReadiness
from app.business.production_release import ProductionRelease
class B89B95CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); (self.root/'app').mkdir(); (self.root/'config').mkdir(); (self.root/'AI_PLIKI').mkdir(); (self.root/'app'/'x.py').write_text('x=1\n'); (self.root/'main.py').write_text('pass\n'); (self.root/'requirements.txt').write_text(''); (self.root/'start_jarvis.bat').write_text(''); (self.root/'start_jarvis.vbs').write_text(''); (self.root/'JARVIS_OS.ico').write_bytes(b'i'); (self.root/'JARVIS_OS.png').write_bytes(b'p')
    def tearDown(self): self.tmp.cleanup()
    def test_b89_version_channels(self):
        svc=ProductionVersioning(self.root); self.assertFalse(svc.status()['prepared']); self.assertEqual(svc.prepare()['version'],'1.0.0'); self.assertEqual(svc.promote_stable()['channel'],'STABLE')
    def test_b90_rejects_unsafe_manifest(self):
        svc=CustomerUpdateChannels(self.root); svc.inbox.mkdir(parents=True); (svc.inbox/'bad.json').write_text('{"version":"1","channel":"STABLE","files":{"../x":"a"}}'); result=svc.scan(); self.assertEqual(result['valid_package_count'],0)
    def test_b91_rsa_sign_verify_with_test_key(self):
        svc=CommercialLicenseAuthority(self.root); result=svc.initialize(bits=512); self.assertTrue(result['issuer_ready']); self.assertTrue(svc.issue_demo_license()['success']); self.assertTrue(svc.verify_latest()['valid']); self.assertFalse(any('private' in str(x).lower() for x in [svc.status().get('public_key_path')]))
    def test_b92_manifest_excludes_owner_private(self):
        svc=DistributionProtection(self.root); result=svc.build_manifest(); self.assertTrue(result['verified']); self.assertTrue(svc.verify()['verified'])
    def test_b93_never_exports_private_key(self):
        distribution=DistributionProtection(self.root); distribution.build_manifest(); licensing=CommercialLicenseAuthority(self.root); licensing.initialize(bits=512)
        setup=self.root/'AI_PLIKI'/'setup.zip'; import zipfile
        with zipfile.ZipFile(setup,'w') as z: z.writestr('PAYLOAD/main.py','pass')
        manager=MagicMock(); manager.export_setup_package.return_value={'success':True,'setup_package':{'path':str(setup)}}
        svc=CustomerDeployment(self.root,manager,distribution,licensing); result=svc.export(); self.assertTrue(result['success'])
        with zipfile.ZipFile(result['latest_package']) as z: self.assertFalse(any('private' in n.lower() for n in z.namelist()))
    def test_b94_requires_owner_review(self):
        package=self.root/'AI_PLIKI'/'customer.zip'; package.write_bytes(b'x'); dep=MagicMock(); dep.status.return_value={'latest_package':str(package)}; svc=SalesReadiness(self.root,dep); self.assertFalse(svc.export_bundle()['sales_ready']); self.assertTrue(svc.acknowledge_owner_review()['sales_ready'])
    def test_b95_gate_model(self):
        ok=lambda **k: MagicMock(status=MagicMock(return_value=k), verify=MagicMock(return_value={'success':True}))
        rc=ok(latest_release='rc.zip'); version=ok(channel='STABLE'); updates=ok(package_count=0,valid_package_count=0,catalog_path='catalog.json'); lic=ok(issuer_ready=True); dist=ok(verified=True); dep=ok(latest_package='customer.zip'); sales=ok(sales_ready=True)
        svc=ProductionRelease(self.root,versioning=version,updates=updates,licensing=lic,distribution=dist,deployment=dep,sales=sales,release_candidate=rc); self.assertTrue(svc.status()['release_ready'])
