from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path, PurePosixPath
from typing import Any
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class CustomerUpdateChannels:
    """B90 local customer update catalog; no network download or execution."""
    CHANNELS=("PILOT","STABLE")
    def __init__(self, project_root: str | Path) -> None:
        self.paths=ProjectPaths.from_value(project_root); self.inbox=self.paths.ai_files/'customer_updates'; self.path=self.paths.data/'business'/'customer_update_channels.json'; self.catalog=self.inbox/'CUSTOMER_UPDATE_CATALOG.json'; self._store=JsonStore(self.path,self._default)
    def status(self)->dict[str,Any]:
        data=self._normalize(self._store.load()); self._store.save(data); return self._response("CUSTOMER_UPDATE_CHANNELS_STATUS",data)
    def scan(self)->dict[str,Any]:
        self.inbox.mkdir(parents=True,exist_ok=True); packages=[]
        for manifest in sorted(self.inbox.glob('*.json')):
            if manifest.name==self.catalog.name: continue
            packages.append(self._inspect(manifest))
        data=self._normalize(self._store.load()); data['packages']=packages[-100:]; data['scanned_at']=self._now(); data['cycles']+=1; self._store.save(data)
        response=self._response("CUSTOMER_UPDATE_SCAN_COMPLETED",data); response['decision']='CLEAR' if not any(not x['valid'] for x in packages) else 'REVIEW'; return response
    def export_catalog(self)->dict[str,Any]:
        data=self._normalize(self._store.load()); self.inbox.mkdir(parents=True,exist_ok=True)
        payload={"schema_version":1,"type":"JARVIS_CUSTOMER_UPDATE_CATALOG","generated_at":self._now(),"packages":[x for x in data['packages'] if x.get('valid')]}
        temp=self.catalog.with_suffix('.json.tmp'); temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(self.catalog)
        data['catalog_path']=str(self.catalog); self._store.save(data); response=self._response("CUSTOMER_UPDATE_CATALOG_EXPORTED",data); response['decision']='EXPORTED'; return response
    def _inspect(self,path:Path)->dict[str,Any]:
        try: payload=json.loads(path.read_text(encoding='utf-8'))
        except Exception as e: return {"manifest":str(path),"valid":False,"errors":[type(e).__name__]}
        channel=str(payload.get('channel','')).upper(); version=str(payload.get('version','')).strip(); files=payload.get('files',{})
        errors=[]
        if channel not in self.CHANNELS: errors.append('INVALID_CHANNEL')
        if not version: errors.append('MISSING_VERSION')
        if not isinstance(files,dict): errors.append('INVALID_FILES')
        else:
            for rel,digest in files.items():
                pure=PurePosixPath(str(rel).replace('\\','/'))
                if pure.is_absolute() or '..' in pure.parts or not str(digest): errors.append('UNSAFE_FILE'); break
        return {"manifest":str(path),"version":version,"channel":channel,"valid":not errors,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"errors":errors}
    def _response(self,status,data):
        valid=sum(1 for x in data['packages'] if x.get('valid')); return {"success":True,"status":status,"operation":"customer_update_channels","stage":"B90","runtime":{"phase":"READY","running":False,"paused":False,"cycles_completed":data['cycles'],"last_decision":"READY"},"package_count":len(data['packages']),"valid_package_count":valid,"packages":data['packages'][-20:],"catalog_path":data.get('catalog_path'),"decision":"READY","reason":"Kanały aktualizacji klientów działają wyłącznie lokalnie.","report_path":str(self.path),"errors":[]}
    def _default(self): return {"schema_version":1,"packages":[],"cycles":0,"scanned_at":None,"catalog_path":None}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"packages":[x for x in d.get('packages',[]) if isinstance(x,dict)][-100:],"cycles":max(0,int(d.get('cycles',0))),"scanned_at":d.get('scanned_at'),"catalog_path":d.get('catalog_path')}
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
