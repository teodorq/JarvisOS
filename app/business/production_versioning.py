from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class ProductionVersioning:
    """B89 deterministic production version and release-channel registry."""
    VERSION = "1.0.0"
    CHANNELS = ("OWNER", "PILOT", "STABLE")
    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "production_versioning.json"
        self._store = JsonStore(self.path, self._default)
    def status(self) -> dict[str, Any]:
        data=self._normalize(self._store.load()); self._store.save(data)
        return self._response("PRODUCTION_VERSIONING_STATUS", data, "READY")
    def prepare(self) -> dict[str, Any]:
        data=self._normalize(self._store.load())
        data.update({"version":self.VERSION,"channel":"OWNER","prepared":True,"prepared_at":self._now()})
        self._event(data,"PRODUCTION_VERSION_PREPARED"); self._store.save(data)
        return self._response("PRODUCTION_VERSION_PREPARED", data, "PREPARED")
    def promote_pilot(self) -> dict[str, Any]: return self._promote("PILOT")
    def promote_stable(self) -> dict[str, Any]: return self._promote("STABLE")
    def _promote(self, channel: str) -> dict[str, Any]:
        data=self._normalize(self._store.load())
        if not data["prepared"]: return self._error("VERSION_NOT_PREPARED", "Najpierw przygotuj wersję produkcyjną B89.")
        data["channel"]=channel; data["promoted_at"]=self._now(); self._event(data,f"CHANNEL_{channel}"); self._store.save(data)
        return self._response("PRODUCTION_CHANNEL_PROMOTED", data, channel)
    def _response(self,status,data,decision):
        return {"success":True,"status":status,"operation":"production_versioning","stage":"B89","runtime":{"phase":"READY" if data['prepared'] else "IDLE","running":False,"paused":False,"cycles_completed":len(data['history']),"last_decision":decision},"version":data['version'],"channel":data['channel'],"prepared":data['prepared'],"history":data['history'][-10:],"decision":decision,"reason":"Wersjonowanie produkcyjne i kanały są kontrolowane lokalnie.","report_path":str(self.path),"errors":[]}
    def _error(self,status,msg): return {"success":False,"status":status,"operation":"production_versioning","stage":"B89","runtime":{"phase":"ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":0,"last_decision":"REJECT"},"decision":"REJECT","reason":msg,"report_path":str(self.path),"errors":[msg]}
    def _default(self): return {"schema_version":1,"version":"1.0.0","channel":"OWNER","prepared":False,"prepared_at":None,"promoted_at":None,"history":[]}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"version":str(d.get('version','1.0.0')),"channel":str(d.get('channel','OWNER')).upper() if str(d.get('channel','OWNER')).upper() in self.CHANNELS else 'OWNER',"prepared":bool(d.get('prepared',False)),"prepared_at":d.get('prepared_at'),"promoted_at":d.get('promoted_at'),"history":[x for x in d.get('history',[]) if isinstance(x,dict)][-50:]}
    def _event(self,d,action): d['history'].append({"timestamp":self._now(),"action":action,"version":d['version'],"channel":d['channel']}); d['history']=d['history'][-50:]
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
