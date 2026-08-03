from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path
from typing import Any, Iterable
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class DistributionProtection:
    """B92 distribution manifest and secret-leak prevention (not DRM)."""
    FORBIDDEN=("data/business/owner_private","archive/","tests/","AI_PLIKI/")
    def __init__(self, project_root:str|Path)->None:
        self.paths=ProjectPaths.from_value(project_root); self.path=self.paths.data/'business'/'distribution_protection.json'; self.manifest=self.paths.ai_files/'distribution'/'JARVIS_DISTRIBUTION_MANIFEST.json'; self._store=JsonStore(self.path,self._default)
    def status(self)->dict[str,Any]:
        d=self._normalize(self._store.load()); self._store.save(d); return {"success":True,"status":"DISTRIBUTION_PROTECTION_STATUS","operation":"distribution_protection","stage":"B92","runtime":{"phase":"READY" if d['verified'] else "IDLE","running":False,"paused":False,"cycles_completed":d['cycles'],"last_decision":"VERIFIED" if d['verified'] else "PREPARE"},"verified":d['verified'],"file_count":d['file_count'],"manifest_path":d.get('manifest_path'),"decision":"VERIFIED" if d['verified'] else "PREPARE","reason":"Manifest chroni integralność i blokuje eksport danych właściciela; nie jest szyfrowaniem ani DRM.","report_path":str(self.path),"errors":d['errors']}
    def build_manifest(self)->dict[str,Any]:
        files={}; errors=[]
        for path,rel in self._iter_files():
            if any(rel.startswith(prefix) for prefix in self.FORBIDDEN): errors.append(f'FORBIDDEN:{rel}'); continue
            files[rel]=hashlib.sha256(path.read_bytes()).hexdigest()
        payload={"schema_version":1,"type":"JARVIS_DISTRIBUTION_MANIFEST","generated_at":self._now(),"algorithm":"SHA-256","purpose":"integrity-and-secret-exclusion-not-drm","files":files,"forbidden_prefixes":list(self.FORBIDDEN)}
        self.manifest.parent.mkdir(parents=True,exist_ok=True); tmp=self.manifest.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.manifest)
        d=self._normalize(self._store.load()); d.update({"verified":not errors,"file_count":len(files),"manifest_path":str(self.manifest),"errors":errors,"cycles":d['cycles']+1}); self._store.save(d); return self.status() | {"status":"DISTRIBUTION_MANIFEST_CREATED","decision":"VERIFIED" if not errors else "REVIEW"}
    def verify(self)->dict[str,Any]:
        if not self.manifest.is_file(): return self._error('DISTRIBUTION_MANIFEST_MISSING','Najpierw zbuduj manifest dystrybucji B92.')
        payload=json.loads(self.manifest.read_text(encoding='utf-8')); changed=[]; missing=[]
        for rel,digest in dict(payload.get('files',{})).items():
            path=(self.paths.root/rel).resolve(strict=False)
            try: path.relative_to(self.paths.root.resolve(strict=False))
            except ValueError: changed.append(rel); continue
            if not path.is_file(): missing.append(rel)
            elif hashlib.sha256(path.read_bytes()).hexdigest()!=digest: changed.append(rel)
        d=self._normalize(self._store.load()); d['verified']=not changed and not missing; d['errors']=[*(f'CHANGED:{x}' for x in changed),*(f'MISSING:{x}' for x in missing)]; d['cycles']+=1; self._store.save(d); return self.status() | {"status":"DISTRIBUTION_MANIFEST_VERIFIED" if d['verified'] else "DISTRIBUTION_MANIFEST_CHANGED"}
    def _iter_files(self)->Iterable[tuple[Path,str]]:
        for base in ('app','config'):
            for p in sorted((self.paths.root/base).rglob('*')):
                if p.is_file() and not p.is_symlink() and p.suffix.lower() not in {'.pyc','.tmp','.log'}:
                    yield p,p.relative_to(self.paths.root).as_posix()
        for name in ('main.py','requirements.txt','start_jarvis.bat','JARVIS_OS.ico','JARVIS_OS.png'):
            p=self.paths.root/name
            if p.is_file(): yield p,name
    def _default(self): return {"schema_version":1,"verified":False,"file_count":0,"manifest_path":None,"errors":[],"cycles":0}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"verified":bool(d.get('verified',False)),"file_count":max(0,int(d.get('file_count',0))),"manifest_path":d.get('manifest_path'),"errors":[str(x) for x in d.get('errors',[])][:50],"cycles":max(0,int(d.get('cycles',0)))}
    def _error(self,status,msg): return {"success":False,"status":status,"operation":"distribution_protection","stage":"B92","runtime":{"phase":"ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":0,"last_decision":"REJECT"},"decision":"REJECT","reason":msg,"report_path":str(self.path),"errors":[msg]}
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
