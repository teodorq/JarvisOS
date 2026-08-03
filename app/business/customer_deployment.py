from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from typing import Any
import zipfile
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class CustomerDeployment:
    """B93 exports a customer handoff without owner-private material."""
    def __init__(self, project_root:str|Path, installation_manager, distribution, licensing)->None:
        self.paths=ProjectPaths.from_value(project_root); self.installation_manager=installation_manager; self.distribution=distribution; self.licensing=licensing; self.path=self.paths.data/'business'/'customer_deployment.json'; self.export_dir=self.paths.ai_files/'customer_delivery'; self._store=JsonStore(self.path,self._default)
    def status(self)->dict[str,Any]:
        d=self._normalize(self._store.load()); latest=Path(str(d.get('latest_package') or '')); ready=latest.is_file(); return {"success":True,"status":"CUSTOMER_DEPLOYMENT_STATUS","operation":"customer_deployment","stage":"B93","runtime":{"phase":"READY" if ready else "IDLE","running":False,"paused":False,"cycles_completed":d['exports'],"last_decision":"READY" if ready else "BUILD"},"package_count":d['exports'],"latest_package":str(latest) if ready else None,"latest_sha256":d.get('latest_sha256'),"decision":"READY" if ready else "BUILD","reason":"Paczka klienta nie zawiera klucza prywatnego ani danych właściciela.","report_path":str(self.path),"errors":[]}
    def export(self)->dict[str,Any]:
        if not self.distribution.status().get('verified'): return self._error('DISTRIBUTION_NOT_VERIFIED','Najpierw zbuduj i zweryfikuj manifest B92.')
        if not self.licensing.status().get('issuer_ready'): return self._error('LICENSE_ISSUER_NOT_READY','Najpierw zainicjalizuj B91.')
        setup=self.installation_manager.export_setup_package(); record=dict(setup.get('setup_package',{}) or {}); setup_path=Path(str(record.get('path','')))
        if not setup.get('success') or not setup_path.is_file(): return self._error('SETUP_PACKAGE_MISSING','Nie udało się utworzyć pakietu B87.')
        self.export_dir.mkdir(parents=True,exist_ok=True); target=self.export_dir/'JARVIS_OS_BUSINESS_CUSTOMER_1_0_0.zip'; tmp=target.with_suffix('.zip.tmp'); tmp.unlink(missing_ok=True)
        metadata={"schema_version":1,"type":"JARVIS_CUSTOMER_DELIVERY","version":"1.0.0","created_at":self._now(),"setup_sha256":hashlib.sha256(setup_path.read_bytes()).hexdigest(),"license_workflow":"OFFLINE_SIGNED_LICENSE_REQUIRED","owner_private_included":False}
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.write(setup_path,setup_path.name); z.write(self.licensing.public_path,'COMMERCIAL_PUBLIC_KEY.json'); z.write(self.distribution.manifest,'JARVIS_DISTRIBUTION_MANIFEST.json'); z.writestr('CUSTOMER_DELIVERY.json',json.dumps(metadata,ensure_ascii=False,indent=2)); z.writestr('README_CUSTOMER.txt','JARVIS OS 1.0.0\n\n1. Rozpakuj pakiet instalacyjny.\n2. Uruchom instalator.\n3. Wygeneruj wniosek aktywacyjny.\n4. Wgraj podpisaną licencję offline.\n')
            if any('owner_private' in n.casefold() for n in z.namelist()): raise RuntimeError('owner private leak')
        tmp.replace(target); d=self._normalize(self._store.load()); d['exports']+=1; d['latest_package']=str(target); d['latest_sha256']=hashlib.sha256(target.read_bytes()).hexdigest(); self._store.save(d); return self.status() | {"status":"CUSTOMER_DEPLOYMENT_EXPORTED","decision":"EXPORTED"}
    def verify(self)->dict[str,Any]:
        d=self._normalize(self._store.load()); path=Path(str(d.get('latest_package') or ''))
        if not path.is_file(): return self._error('CUSTOMER_PACKAGE_MISSING','Brak paczki klienta.')
        valid=hashlib.sha256(path.read_bytes()).hexdigest()==d.get('latest_sha256')
        with zipfile.ZipFile(path) as z: valid=valid and z.testzip() is None and not any('owner_private' in n.casefold() for n in z.namelist())
        return self.status() | {"success":valid,"status":"CUSTOMER_DEPLOYMENT_VERIFIED" if valid else "CUSTOMER_DEPLOYMENT_INVALID","decision":"VERIFIED" if valid else "REJECT","errors":[] if valid else ['PACKAGE_INVALID']}
    def _default(self): return {"schema_version":1,"exports":0,"latest_package":None,"latest_sha256":None}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"exports":max(0,int(d.get('exports',0))),"latest_package":d.get('latest_package'),"latest_sha256":d.get('latest_sha256')}
    def _error(self,status,msg): return {"success":False,"status":status,"operation":"customer_deployment","stage":"B93","runtime":{"phase":"ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":0,"last_decision":"REJECT"},"decision":"REJECT","reason":msg,"report_path":str(self.path),"errors":[msg]}
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
