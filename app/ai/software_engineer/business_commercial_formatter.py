from __future__ import annotations
from typing import Any
def format_business_commercial_response(r:dict[str,Any])->str:
    stage=str(r.get('stage','B89-B95')); runtime=dict(r.get('runtime',{}) or {}); lines=[f"JARVIS Business {stage}: {r.get('status','UNKNOWN')}",f"Faza: {runtime.get('phase','IDLE')}"]
    if stage=='B89': lines+= [f"Wersja: {r.get('version','-')} | kanał {r.get('channel','OWNER')}",f"Przygotowana: {'TAK' if r.get('prepared') else 'NIE'}"]
    elif stage=='B90': lines+=[f"Pakiety klientów: {r.get('package_count',0)} | poprawne {r.get('valid_package_count',0)}",f"Katalog: {r.get('catalog_path') or 'Brak'}"]
    elif stage=='B91': lines+=[f"Wystawca: {'GOTOWY' if r.get('issuer_ready') else 'NIEZAINICJALIZOWANY'}",f"Wydane licencje: {r.get('issued_count',0)}",f"Klucz publiczny: {r.get('public_key_path','-')}"]
    elif stage=='B92': lines+=[f"Manifest: {'ZWERYFIKOWANY' if r.get('verified') else 'WYMAGA PRZYGOTOWANIA'} | pliki {r.get('file_count',0)}"]
    elif stage=='B93': lines+=[f"Paczki klienta: {r.get('package_count',0)}",f"Ostatnia: {r.get('latest_package') or 'Brak'}"]
    elif stage=='B94':
        gates=dict(r.get('gates',{}) or {}); lines+=[f"Gotowość sprzedażowa: {'TAK' if r.get('sales_ready') else 'NIE'}",f"Bramki: {sum(bool(v) for v in gates.values())}/{len(gates)}"]
    elif stage=='B95':
        gates=dict(r.get('gates',{}) or {}); lines+=[f"Wydanie {r.get('version','1.0.0')} | bramki {sum(bool(v) for v in gates.values())}/{len(gates)}",f"Ostatnie: {r.get('latest_release') or 'Brak'}"]
    elif stage=='B89-B95':
        stages=dict(r.get('stages',{}) or {}); lines.append('Etapy: '+', '.join(f"{k}:{dict(v.get('runtime',{}) or {}).get('phase','IDLE')}" for k,v in stages.items()))
    if r.get('decision'): lines.append(f"Decyzja: {r['decision']}")
    if r.get('reason'): lines.append(f"Uzasadnienie: {r['reason']}")
    for e in r.get('errors',[])[:8]: lines.append(f"Błąd: {e}")
    lines.append('Bezpieczeństwo: brak automatycznej publikacji; operacje zapisu wymagają potwierdzenia.')
    return '\n'.join(lines)
