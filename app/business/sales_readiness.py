from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from typing import Any
import zipfile
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class SalesReadiness:
    """B94 technical sales handoff; legal templates still require owner review."""
    def __init__(self, project_root:str|Path, deployment)->None:
        self.paths=ProjectPaths.from_value(project_root); self.deployment=deployment; self.path=self.paths.data/'business'/'sales_readiness.json'; self.export_dir=self.paths.ai_files/'sales_handoff'; self._store=JsonStore(self.path,self._default)
    def status(self)->dict[str,Any]:
        d=self._normalize(self._store.load()); package=Path(str(d.get('latest_bundle') or '')); gates={"customer_package":bool(self.deployment.status().get('latest_package')),"support_guide":package.is_file(),"owner_review":d['owner_review']}; ready=all(gates.values())
        return {"success":True,"status":"SALES_READINESS_STATUS","operation":"sales_readiness","stage":"B94","runtime":{"phase":"READY" if ready else "ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":d['exports'],"last_decision":"READY" if ready else "REVIEW"},"gates":gates,"sales_ready":ready,"latest_bundle":str(package) if package.is_file() else None,"decision":"READY" if ready else "REVIEW","reason":"Dokumenty są szablonami technicznymi; warunki prawne wymagają osobnej weryfikacji właściciela.","report_path":str(self.path),"errors":[k for k,v in gates.items() if not v]}
    def export_bundle(self)->dict[str,Any]:
        customer=Path(str(self.deployment.status().get('latest_package') or ''))
        if not customer.is_file(): return self._error('CUSTOMER_PACKAGE_MISSING','Najpierw wyeksportuj paczkę klienta B93.')
        self.export_dir.mkdir(parents=True,exist_ok=True); target=self.export_dir/'JARVIS_OS_BUSINESS_SALES_HANDOFF_1_0_0.zip'; tmp=target.with_suffix('.zip.tmp'); tmp.unlink(missing_ok=True)
        checklist={"schema_version":1,"type":"JARVIS_SALES_HANDOFF","created_at":self._now(),"customer_package":customer.name,"customer_sha256":hashlib.sha256(customer.read_bytes()).hexdigest(),"legal_review_required":True}
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.write(customer,customer.name); z.writestr('SALES_CHECKLIST.json',json.dumps(checklist,ensure_ascii=False,indent=2)); z.writestr('README_SALES_HANDOFF.txt','JARVIS OS — PAKIET SPRZEDAŻOWY\n\nZawiera techniczną paczkę klienta.\nSzablony EULA, polityki prywatności, ceny i warunki wsparcia muszą zostać sprawdzone przez właściciela oraz prawnika przed sprzedażą.\n'); z.writestr('ACTIVATION_GUIDE.txt','Aktywacja odbywa się offline przez podpisaną licencję B91. Klucz prywatny nie jest przekazywany klientowi.\n')
        tmp.replace(target); d=self._normalize(self._store.load()); d['exports']+=1; d['latest_bundle']=str(target); d['owner_review']=False; self._store.save(d); return self.status() | {"status":"SALES_HANDOFF_EXPORTED","decision":"PREVIEW_READY"}
    def acknowledge_owner_review(self)->dict[str,Any]:
        d=self._normalize(self._store.load())
        if not Path(str(d.get('latest_bundle') or '')).is_file(): return self._error('SALES_BUNDLE_MISSING','Najpierw wyeksportuj pakiet sprzedażowy B94.')
        d['owner_review']=True; d['reviewed_at']=self._now(); self._store.save(d); return self.status() | {"status":"SALES_OWNER_REVIEW_ACKNOWLEDGED","decision":"ACKNOWLEDGED"}
    def _default(self): return {"schema_version":1,"exports":0,"latest_bundle":None,"owner_review":False,"reviewed_at":None}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"exports":max(0,int(d.get('exports',0))),"latest_bundle":d.get('latest_bundle'),"owner_review":bool(d.get('owner_review',False)),"reviewed_at":d.get('reviewed_at')}
    def _error(self,status,msg): return {"success":False,"status":status,"operation":"sales_readiness","stage":"B94","runtime":{"phase":"ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":0,"last_decision":"REJECT"},"decision":"REJECT","reason":msg,"report_path":str(self.path),"errors":[msg]}
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
