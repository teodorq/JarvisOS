from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from typing import Any
import zipfile
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class ProductionRelease:
    """B95 final technical GA gates and immutable-by-hash export."""
    VERSION='1.0.0'
    def __init__(self, project_root:str|Path, *, versioning, updates, licensing, distribution, deployment, sales, release_candidate)->None:
        self.paths=ProjectPaths.from_value(project_root); self.versioning=versioning; self.updates=updates; self.licensing=licensing; self.distribution=distribution; self.deployment=deployment; self.sales=sales; self.release_candidate=release_candidate; self.path=self.paths.data/'business'/'production_release.json'; self.export_dir=self.paths.ai_files/'production_release'; self._store=JsonStore(self.path,self._default)
    def status(self)->dict[str,Any]:
        d=self._normalize(self._store.load()); gates={"rc1_verified":bool(self.release_candidate.status().get('latest_release')),"version_stable":self.versioning.status().get('channel')=='STABLE',"update_catalog_ready":bool(self.updates.status().get('catalog_path')) and self.updates.status().get('valid_package_count',0)==self.updates.status().get('package_count',0),"license_issuer_ready":bool(self.licensing.status().get('issuer_ready')),"distribution_verified":bool(self.distribution.status().get('verified')),"customer_package_verified":self.deployment.verify().get('success',False) if self.deployment.status().get('latest_package') else False,"sales_owner_review":bool(self.sales.status().get('sales_ready')),"safety_locked":True}; ready=all(gates.values()); latest=Path(str(d.get('latest_release') or ''))
        return {"success":True,"status":"PRODUCTION_RELEASE_STATUS","operation":"production_release","stage":"B95","runtime":{"phase":"READY" if ready else "ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":d['exports'],"last_decision":"GA_READY" if ready else "GATES_PENDING"},"version":self.VERSION,"gates":gates,"release_ready":ready,"latest_release":str(latest) if latest.is_file() else None,"latest_sha256":d.get('latest_sha256'),"decision":"GA_READY" if ready else "GATES_PENDING","reason":"Gotowość techniczna nie zastępuje przeglądu prawnego, podatkowego i handlowego.","report_path":str(self.path),"errors":[k for k,v in gates.items() if not v]}
    def export(self)->dict[str,Any]:
        current=self.status()
        if not current['release_ready']: return self._error('PRODUCTION_GATES_NOT_READY','Nie wszystkie bramki B95 są spełnione.',current['errors'])
        customer=Path(str(self.deployment.status().get('latest_package'))); sales=Path(str(self.sales.status().get('latest_bundle'))); self.export_dir.mkdir(parents=True,exist_ok=True); target=self.export_dir/'JARVIS_OS_BUSINESS_1_0_0_PRODUCTION.zip'; tmp=target.with_suffix('.zip.tmp'); tmp.unlink(missing_ok=True)
        manifest={"schema_version":1,"type":"JARVIS_PRODUCTION_RELEASE","version":self.VERSION,"created_at":self._now(),"customer_sha256":hashlib.sha256(customer.read_bytes()).hexdigest(),"sales_sha256":hashlib.sha256(sales.read_bytes()).hexdigest(),"gates":current['gates'],"technical_release_only":True}
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z: z.write(customer,customer.name); z.write(sales,sales.name); z.writestr('JARVIS_PRODUCTION_RELEASE.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        tmp.replace(target); d=self._normalize(self._store.load()); d['exports']+=1; d['latest_release']=str(target); d['latest_sha256']=hashlib.sha256(target.read_bytes()).hexdigest(); self._store.save(d); return self.status() | {"status":"PRODUCTION_RELEASE_EXPORTED","decision":"EXPORTED"}
    def verify(self)->dict[str,Any]:
        d=self._normalize(self._store.load()); p=Path(str(d.get('latest_release') or ''))
        if not p.is_file(): return self._error('PRODUCTION_RELEASE_MISSING','Brak eksportu produkcyjnego B95.')
        valid=hashlib.sha256(p.read_bytes()).hexdigest()==d.get('latest_sha256')
        with zipfile.ZipFile(p) as z: valid=valid and z.testzip() is None
        return self.status() | {"success":valid,"status":"PRODUCTION_RELEASE_VERIFIED" if valid else "PRODUCTION_RELEASE_INVALID","decision":"VERIFIED" if valid else "REJECT","errors":[] if valid else ['SHA256_OR_ZIP_FAILED']}
    def _default(self): return {"schema_version":1,"exports":0,"latest_release":None,"latest_sha256":None}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"exports":max(0,int(d.get('exports',0))),"latest_release":d.get('latest_release'),"latest_sha256":d.get('latest_sha256')}
    def _error(self,status,msg,errors=None): return {"success":False,"status":status,"operation":"production_release","stage":"B95","runtime":{"phase":"ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":0,"last_decision":"REJECT"},"decision":"REJECT","reason":msg,"report_path":str(self.path),"errors":list(errors or [msg])}
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
