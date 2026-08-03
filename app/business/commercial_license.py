from __future__ import annotations
from datetime import datetime, timedelta, timezone
import base64, hashlib, json, math, secrets
from pathlib import Path
from typing import Any
from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

class CommercialLicenseAuthority:
    """B91 offline RSA license issuer. Private key stays in owner-only data."""
    E=65537
    def __init__(self, project_root: str | Path) -> None:
        self.paths=ProjectPaths.from_value(project_root); self.private_path=self.paths.data/'business'/'owner_private'/'commercial_private_key.json'; self.public_path=self.paths.root/'config'/'commercial_public_key.json'; self.licenses=self.paths.ai_files/'commercial_licenses'; self.path=self.paths.data/'business'/'commercial_license_authority.json'; self._store=JsonStore(self.path,self._default)
    def status(self)->dict[str,Any]:
        data=self._normalize(self._store.load()); self._store.save(data); ready=self.private_path.is_file() and self.public_path.is_file()
        return {"success":True,"status":"COMMERCIAL_LICENSE_AUTHORITY_STATUS","operation":"commercial_license","stage":"B91","runtime":{"phase":"READY" if ready else "IDLE","running":False,"paused":False,"cycles_completed":data['issued_count'],"last_decision":"READY" if ready else "INITIALIZE"},"issuer_ready":ready,"issued_count":data['issued_count'],"public_key_path":str(self.public_path),"private_key_exported":False,"latest_license":data.get('latest_license'),"decision":"READY" if ready else "INITIALIZE","reason":"Klucz prywatny pozostaje lokalnie i nie trafia do paczek klientów.","report_path":str(self.path),"errors":[]}
    def initialize(self, bits:int=2048)->dict[str,Any]:
        if self.private_path.is_file() and self.public_path.is_file(): return self.status() | {"status":"COMMERCIAL_LICENSE_AUTHORITY_ALREADY_INITIALIZED"}
        p=self._prime(bits//2); q=self._prime(bits//2)
        while q==p: q=self._prime(bits//2)
        n=p*q; phi=(p-1)*(q-1); d=pow(self.E,-1,phi); kid=hashlib.sha256(str(n).encode()).hexdigest()[:16].upper()
        private={"schema_version":1,"algorithm":"RSA-PKCS1-v1_5-SHA256","key_id":kid,"n":str(n),"e":self.E,"d":str(d),"created_at":self._now()}; public={k:private[k] for k in ('schema_version','algorithm','key_id','n','e','created_at')}
        self.private_path.parent.mkdir(parents=True,exist_ok=True); self.public_path.parent.mkdir(parents=True,exist_ok=True); self.private_path.write_text(json.dumps(private,indent=2),encoding='utf-8'); self.public_path.write_text(json.dumps(public,indent=2),encoding='utf-8')
        return self.status() | {"status":"COMMERCIAL_LICENSE_AUTHORITY_INITIALIZED","decision":"INITIALIZED"}
    def issue_demo_license(self)->dict[str,Any]:
        if not self.private_path.is_file(): return self._error('LICENSE_AUTHORITY_NOT_INITIALIZED','Najpierw zainicjalizuj wystawcę licencji B91.')
        key=json.loads(self.private_path.read_text(encoding='utf-8')); now=datetime.now(timezone.utc); payload={"schema_version":1,"type":"JARVIS_COMMERCIAL_LICENSE","license_id":"LIC-"+secrets.token_hex(8).upper(),"product_code":"JARVIS-OS-BUSINESS","organization":"CUSTOMER DEMO","edition":"BUSINESS","seats":1,"issued_at":now.isoformat(),"expires_at":(now+timedelta(days=30)).isoformat(),"key_id":key['key_id']}
        message=self._canonical(payload); signature=self._sign(message,int(key['n']),int(key['d']))
        package={"payload":payload,"signature":base64.b64encode(signature).decode('ascii'),"algorithm":key['algorithm']}; self.licenses.mkdir(parents=True,exist_ok=True); target=self.licenses/f"{payload['license_id']}.json"; target.write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
        data=self._normalize(self._store.load()); data['issued_count']+=1; data['latest_license']=str(target); self._store.save(data)
        return self.status() | {"status":"COMMERCIAL_LICENSE_ISSUED","decision":"ISSUED","license_path":str(target)}
    def verify_latest(self)->dict[str,Any]:
        data=self._normalize(self._store.load()); path=Path(str(data.get('latest_license') or ''))
        if not path.is_file() or not self.public_path.is_file(): return self._error('COMMERCIAL_LICENSE_MISSING','Brak licencji lub klucza publicznego.')
        package=json.loads(path.read_text(encoding='utf-8')); public=json.loads(self.public_path.read_text(encoding='utf-8')); payload=dict(package.get('payload',{})); sig=base64.b64decode(str(package.get('signature','')),validate=True); valid=self._verify(self._canonical(payload),sig,int(public['n']),int(public['e']))
        return {"success":valid,"status":"COMMERCIAL_LICENSE_VERIFIED" if valid else "COMMERCIAL_LICENSE_INVALID","operation":"commercial_license","stage":"B91","runtime":{"phase":"READY" if valid else "ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":data['issued_count'],"last_decision":"VERIFIED" if valid else "REJECT"},"valid":valid,"license":payload,"decision":"VERIFIED" if valid else "REJECT","reason":"Podpis RSA jest poprawny." if valid else "Podpis licencji jest niepoprawny.","report_path":str(path),"errors":[] if valid else ['INVALID_SIGNATURE']}
    @staticmethod
    def _canonical(payload): return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    @staticmethod
    def _emsa(message,k):
        digest=hashlib.sha256(message).digest(); prefix=bytes.fromhex('3031300d060960864801650304020105000420'); t=prefix+digest
        if k<len(t)+11: raise ValueError('RSA key too short')
        return b'\x00\x01'+b'\xff'*(k-len(t)-3)+b'\x00'+t
    @classmethod
    def _sign(cls,message,n,d):
        k=(n.bit_length()+7)//8; em=cls._emsa(message,k); return pow(int.from_bytes(em,'big'),d,n).to_bytes(k,'big')
    @classmethod
    def _verify(cls,message,signature,n,e):
        k=(n.bit_length()+7)//8
        if len(signature)!=k: return False
        em=pow(int.from_bytes(signature,'big'),e,n).to_bytes(k,'big')
        return secrets.compare_digest(em,cls._emsa(message,k))
    @classmethod
    def _prime(cls,bits):
        while True:
            n=secrets.randbits(bits)|(1<<(bits-1))|1
            if cls._is_prime(n): return n
    @staticmethod
    def _is_prime(n):
        small=(2,3,5,7,11,13,17,19,23,29,31,37)
        for p in small:
            if n%p==0: return n==p
        d=n-1; s=0
        while d%2==0: s+=1; d//=2
        for _ in range(32):
            a=secrets.randbelow(n-3)+2; x=pow(a,d,n)
            if x in (1,n-1): continue
            for _ in range(s-1):
                x=pow(x,2,n)
                if x==n-1: break
            else: return False
        return True
    def _default(self): return {"schema_version":1,"issued_count":0,"latest_license":None}
    def _normalize(self,v):
        d=dict(v or {}) if isinstance(v,dict) else {}; return {"schema_version":1,"issued_count":max(0,int(d.get('issued_count',0))),"latest_license":d.get('latest_license')}
    def _error(self,status,msg): return {"success":False,"status":status,"operation":"commercial_license","stage":"B91","runtime":{"phase":"ATTENTION_REQUIRED","running":False,"paused":False,"cycles_completed":0,"last_decision":"REJECT"},"decision":"REJECT","reason":msg,"report_path":str(self.path),"errors":[msg]}
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
