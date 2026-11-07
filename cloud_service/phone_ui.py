from __future__ import annotations

from html import escape


PHONE_MANIFEST = r'''{
  "name": "JARVIS OS",
  "short_name": "JARVIS OS",
  "description": "Bezpieczny most telefonu do prywatnego asystenta JARVIS OS.",
  "start_url": "/phone",
  "scope": "/phone",
  "display": "standalone",
  "background_color": "#020b13",
  "theme_color": "#03121f",
  "icons": [{"src": "/phone-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}]
}'''

PHONE_ICON = r'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="108" fill="#020b13"/><circle cx="256" cy="256" r="182" fill="none" stroke="#31cce9" stroke-width="18"/><path d="M164 352 227 156h58l63 196h-48l-13-45h-65l-13 45zm70-86h41l-20-70z" fill="#dff7ff"/><circle cx="256" cy="256" r="222" fill="none" stroke="#0e6281" stroke-width="8" stroke-dasharray="12 24"/></svg>'''

PHONE_SERVICE_WORKER = r'''"use strict";
const CACHE="jarvis-os-phone-v4",OFFLINE="/phone-offline";
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.add(OFFLINE)));self.skipWaiting()});
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",event=>{const url=new URL(event.request.url);if(event.request.mode==="navigate"&&url.origin===location.origin&&url.pathname==="/phone"){event.respondWith(fetch(event.request).catch(()=>caches.match(OFFLINE)))}});
'''

PHONE_LOGIN_PAGE = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#03121f"><title>JARVIS OS — logowanie</title><style>:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;color:#dff7ff;background:radial-gradient(circle at 50% -10%,#08385a,#020b13 55%);padding:20px}.card{width:min(520px,100%);text-align:center;background:#03131fe8;border:1px solid #0e6281;border-radius:20px;padding:28px;box-shadow:0 14px 50px #0009}h1{letter-spacing:.2em;margin:0 0 8px}p{color:#91bbca;line-height:1.55}.button{display:block;margin-top:22px;border:1px solid #31cce9;border-radius:12px;background:linear-gradient(135deg,#0c7898,#0b4866);color:#fff;padding:14px 18px;font-weight:700;text-decoration:none}.hint{font-size:12px;color:#739baa}</style></head><body><main class="card"><h1>JARVIS OS</h1><p>Telefon łączy się teraz przez Twoje konto Microsoft. Stały kod parowania nie jest już potrzebny.</p><a class="button" href="/.auth/login/aad?post_login_redirect_uri=%2Fphone">ZALOGUJ PRZEZ MICROSOFT</a><a class="button" href="/mobile-start">NAPRAW BIAŁY EKRAN</a><p class="hint">Sesja wygasa po 60 minutach. Ważne działania nadal wymagają potwierdzenia na komputerze.</p></main></body></html>'''

PHONE_FORBIDDEN_PAGE = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#03121f"><title>JARVIS OS — brak dostępu</title><style>:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#020b13;color:#dff7ff;padding:20px}.card{max-width:520px;text-align:center;border:1px solid #8a3443;border-radius:18px;padding:28px;background:#160b11}a{display:block;margin-top:20px;color:#fff;background:#7b2d3a;border-radius:10px;padding:13px;text-decoration:none}</style></head><body><main class="card"><h1>Brak dostępu</h1><p>To konto nie jest właścicielem JARVIS OS.</p><a href="/mobile-start">WYLOGUJ I ZMIEŃ KONTO</a></main></body></html>'''

PHONE_OFFLINE_PAGE = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#03121f"><title>JARVIS OS — offline</title><style>:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#020b13;color:#dff7ff;text-align:center;padding:24px}p{color:#91bbca}button{border:1px solid #31cce9;border-radius:12px;background:#0b4866;color:white;padding:13px 20px;font-weight:700}</style></head><body><main><h1>JARVIS OS</h1><p>Telefon jest offline. Połącz się z internetem i spróbuj ponownie.</p><button onclick="location.reload()">SPRÓBUJ PONOWNIE</button></main></body></html>'''

PHONE_RECOVERY_PAGE = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>JARVIS OS — start telefonu</title></head><body><main><h1>JARVIS OS</h1><h2>Połączenie z Azure działa</h2><p>Jeśli widzisz ten tekst na iPhonie, naciśnij ikonę kompasu na dole po prawej. Strona otworzy się w pełnym Safari.</p><p>Potem wybierz przycisk logowania poniżej.</p><p><a href="/.auth/login/aad?post_login_redirect_uri=%2Fphone">ZALOGUJ PRZEZ MICROSOFT</a></p><p><a href="/phone">OTWÓRZ JARVIS OS</a></p><hr><p>Wylogowanie poprzedniej sesji wykonuj tylko w pełnym Safari:</p><p><a href="/.auth/logout?post_logout_redirect_uri=%2Fmobile-start">WYLOGUJ POPRZEDNIĄ SESJĘ</a></p></main></body></html>'''
PHONE_START_PAGE = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#03121f"><title>JARVIS OS &mdash; telefon</title>
<style>:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;color:#dff7ff;background:radial-gradient(circle at 50% -10%,#08385a,#020b13 58%)}main{width:min(560px,100%);background:#03131f;border:1px solid #16718d;border-radius:22px;padding:26px;box-shadow:0 18px 60px #000a}h1{margin:0;letter-spacing:.18em;text-align:center}h2{font-size:18px;color:#69e5ff;text-align:center}p,li{color:#a5c8d3;line-height:1.55}.button{display:block;margin:12px 0;border:1px solid #31cce9;border-radius:12px;padding:14px;text-align:center;color:#fff;background:linear-gradient(135deg,#0c7898,#0b4866);font-weight:700;text-decoration:none}.secondary{background:#082739}.danger{border-color:#9f4b5a;background:#38131c}.status{border:1px solid #24556a;border-radius:12px;padding:12px;color:#67f7c7;text-align:center;font-weight:700}.hint{font-size:12px}</style></head>
<body data-page="mobile-start-v3"><main><h1>JARVIS OS</h1><h2>Bezpieczny start telefonu</h2><div class="status">TEN EKRAN POTWIERDZA, &#379;E AZURE DZIA&#321;A</div><p>Na iPhonie otw&oacute;rz t&#281; stron&#281; w pe&#322;nym Safari. Je&#347;li widzisz j&#261; w oknie TikTok, ChatGPT albo innej aplikacji, naci&#347;nij ikon&#281; kompasu lub opcj&#281; <strong>Otw&oacute;rz w Safari</strong>.</p><ol><li>Przejd&#378; do pe&#322;nego Safari.</li><li>Naci&#347;nij przycisk logowania.</li><li>Po zalogowaniu Microsoft wr&oacute;ci do panelu JARVIS OS.</li></ol><a class="button" target="_top" href="/.auth/login/aad?post_login_redirect_uri=%2Fphone">ZALOGUJ PRZEZ MICROSOFT</a><a class="button secondary" href="/phone">OTW&Oacute;RZ PANEL TELEFONU</a><a class="button secondary" href="/mobile-diagnostics">SPRAWD&#377; DIAGNOSTYK&#280;</a><a class="button danger" href="/mobile-logout">WYLOGUJ LUB ZMIE&#323; KONTO</a><p class="hint">Ta strona nie u&#380;ywa JavaScript ani Service Workera, dlatego zawsze pozostaje widoczna i nie wykonuje automatycznych przekierowa&#324;.</p></main></body></html>'''

PHONE_LOGOUT_PAGE = r'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#03121f"><title>JARVIS OS &mdash; wylogowanie</title><style>:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;background:#020b13;color:#dff7ff}main{width:min(520px,100%);border:1px solid #8a3443;border-radius:20px;padding:26px;background:#160b11;text-align:center}p{color:#c9aab1;line-height:1.55}a{display:block;margin:13px 0;border:1px solid #9f4b5a;border-radius:12px;padding:14px;color:#fff;background:#551d29;text-decoration:none;font-weight:700}.secondary{border-color:#176d88;background:#082739}</style></head><body data-page="mobile-logout-v1"><main><h1>Wylogowanie JARVIS OS</h1><p>Azure wyloguje sesj&#281; dopiero po naci&#347;ni&#281;ciu poni&#380;szego przycisku. Strona niczego nie uruchamia automatycznie i nie u&#380;ywa ukrytego zapytania.</p><a target="_top" href="/.auth/logout?post_logout_redirect_uri=%2Fmobile-start">WYLOGUJ SESJ&#280; MICROSOFT</a><a class="secondary" href="/mobile-start">ANULUJ I WR&Oacute;&#262;</a></main></body></html>'''


def phone_login_complete_page(
    *,
    identity_present: bool,
    provider_valid: bool,
    owner_authorized: bool,
    request_id: str,
) -> str:
    if owner_authorized:
        state_class = "ok"
        heading = "SESJA GOTOWA"
        message = (
            "Microsoft potwierdzi&#322; konto w&#322;a&#347;ciciela. "
            "Panel otworzy si&#281; dopiero po dotkni&#281;ciu przycisku."
        )
        primary = '<a class="button" href="/phone">OTW&Oacute;RZ JARVIS OS</a>'
    elif identity_present:
        state_class = "bad"
        heading = "KONTO ODRZUCONE"
        message = (
            "Sesja dotar&#322;a do aplikacji, ale konto lub dostawca nie "
            "spe&#322;nia regu&#322; w&#322;a&#347;ciciela."
        )
        primary = (
            '<a class="button danger" href="/mobile-logout">'
            "WYLOGUJ I ZMIE&#323; KONTO</a>"
        )
    else:
        state_class = "warn"
        heading = "SESJA NIEZAKO&#323;CZONA"
        message = (
            "Azure nie przekaza&#322; jeszcze sesji do aplikacji. "
            "Wr&oacute;&#263; do bezpiecznego startu i wykonaj logowanie "
            "w pe&#322;nym Safari."
        )
        primary = (
            '<a class="button" href="/mobile-start">'
            "WR&Oacute;&#262; DO BEZPIECZNEGO STARTU</a>"
        )
    provider_state = "OK" if provider_valid else "BRAK"
    safe_request_id = escape(request_id)
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#03121f"><title>JARVIS OS &mdash; potwierdzenie sesji</title>
<style>:root{{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}}*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;color:#dff7ff;background:#020b13}}main{{width:min(560px,100%);background:#03131f;border:1px solid #176d88;border-radius:22px;padding:26px;text-align:center}}.state{{margin:18px 0;border:1px solid currentColor;border-radius:12px;padding:13px;font-weight:800;letter-spacing:.08em}}.ok{{color:#67f7c7}}.warn{{color:#ffd77a}}.bad{{color:#ff8c9d}}p{{color:#a5c8d3;line-height:1.55}}.button{{display:block;margin:13px 0;border:1px solid #31cce9;border-radius:12px;padding:14px;color:#fff;background:#0b4866;text-decoration:none;font-weight:700}}.danger{{border-color:#9f4b5a;background:#551d29}}.secondary{{background:#082739}}code{{color:#83d5ed;overflow-wrap:anywhere}}</style></head>
<body data-page="mobile-complete-v1"><main><h1>JARVIS OS</h1><div class="state {state_class}">{heading}</div><p>{message}</p>{primary}<a class="button secondary" href="/mobile-diagnostics">SPRAWD&#377; DIAGNOSTYK&#280;</a><p>Dostawca Entra: <strong>{provider_state}</strong><br>Identyfikator sprawdzenia: <code>{safe_request_id}</code></p><p>Ten ekran nie u&#380;ywa JavaScript, nie przekierowuje automatycznie i nie ujawnia identyfikatora konta.</p></main></body></html>'''


def phone_diagnostics_page(
    *,
    identity_present: bool,
    provider_valid: bool,
    owner_authorized: bool,
    remote_configured: bool,
    storage_verified: bool,
    request_id: str,
    version: str,
    build_sha: str,
) -> str:
    checks = (
        ("Po&#322;&#261;czenie HTTPS z Azure", True),
        ("Sesja Microsoft przekazana do aplikacji", identity_present),
        ("Dostawca logowania Microsoft Entra", provider_valid),
        ("Konto w&#322;a&#347;ciciela JARVIS OS", owner_authorized),
        ("Przeka&#378;nik polece&#324; skonfigurowany", remote_configured),
        ("Dost&#281;p zarz&#261;dzanej to&#380;samo&#347;ci do Storage", storage_verified),
    )
    rows = "".join(
        '<li class="ok">OK &mdash; ' + label + "</li>"
        if passed
        else '<li class="warn">UWAGA &mdash; ' + label + "</li>"
        for label, passed in checks
    )
    safe_request_id = escape(request_id)
    safe_version = escape(version)
    safe_sha = escape(build_sha[:12])
    return f'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#03121f"><title>JARVIS OS &mdash; diagnostyka</title><style>:root{{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:20px;background:#020b13;color:#dff7ff}}main{{width:min(620px,100%);border:1px solid #176d88;border-radius:20px;padding:24px;background:#03131f}}li{{margin:10px 0;line-height:1.45}}.ok{{color:#67f7c7}}.warn{{color:#ffd77a}}code{{color:#83d5ed;overflow-wrap:anywhere}}a{{display:block;margin-top:12px;border:1px solid #31cce9;border-radius:12px;padding:13px;text-align:center;color:#fff;background:#0b4866;text-decoration:none;font-weight:700}}</style></head><body data-page="mobile-diagnostics-v1"><main><h1>Diagnostyka telefonu</h1><ul>{rows}</ul><p>Wersja: <code>{safe_version}</code><br>Obraz: <code>{safe_sha}</code><br>Identyfikator sprawdzenia: <code>{safe_request_id}</code></p><a href="/mobile-start">WR&Oacute;&#262; DO STARTU</a><a href="/phone">OTW&Oacute;RZ PANEL</a></main></body></html>'''


PHONE_PAGE = r'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#03121f"><link rel="manifest" href="/phone.webmanifest"><link rel="icon" href="/phone-icon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/phone-icon.svg"><title>JARVIS OS &mdash; telefon</title>
<style>:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;color:#dff7ff;background:radial-gradient(circle at 50% -10%,#08385a,#020b13 55%)}main{width:min(720px,100%);margin:auto;padding:28px 18px 44px}header{text-align:center;margin-bottom:24px}h1{margin:0;letter-spacing:.22em;font-size:clamp(25px,7vw,40px)}h2{font-size:17px;letter-spacing:.08em;margin:0 0 8px}header p{color:#73cdea;margin:8px 0 0;letter-spacing:.08em}.card{background:#03131fe8;border:1px solid #0e6281;border-radius:18px;padding:18px;box-shadow:0 14px 50px #0009;margin:14px 0}label{display:block;color:#83d5ed;font-size:13px;margin:12px 0 6px}input,textarea,button,.button{width:100%;border-radius:12px;font:inherit}input,textarea{color:#eaffff;background:#010b13;border:1px solid #175f78;padding:13px;outline:none}input:focus,textarea:focus{border-color:#3edbff;box-shadow:0 0 0 3px #1cc8ed22}textarea{min-height:104px;resize:vertical}button,.button{display:block;text-align:center;border:1px solid #31cce9;background:linear-gradient(135deg,#0c7898,#0b4866);color:white;padding:13px 16px;font-weight:700;cursor:pointer;text-decoration:none}button:disabled{opacity:.55;cursor:wait}.quick,.actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 14px}.quick button,.secondary{background:#082739;font-weight:600;padding:10px}.danger{border-color:#e25c70;background:linear-gradient(135deg,#731b2b,#38131c)}.power-confirm{margin-top:12px;padding-top:12px;border-top:1px solid #59303a}.connection{display:flex;align-items:center;gap:9px;border:1px solid #174b60;border-radius:12px;padding:10px 12px;margin-bottom:12px;color:#91bbca;font-size:13px;letter-spacing:.05em}.dot{width:10px;height:10px;border-radius:50%;background:#70838b;box-shadow:0 0 0 4px #70838b18}.dot.checking{background:#ffd77a;box-shadow:0 0 12px #ffd77a}.dot.online{background:#67f7c7;box-shadow:0 0 12px #67f7c7}.dot.offline{background:#ff8c9d;box-shadow:0 0 12px #ff8c9d}.status{min-height:96px;display:grid;align-content:center;text-align:center}.pill{display:inline-block;justify-self:center;padding:6px 12px;border-radius:999px;border:1px solid #176d88;color:#84def4;margin-bottom:10px}#message{white-space:pre-wrap;line-height:1.5}.hint{color:#7aa5b6;font-size:12px;line-height:1.45}.account{display:flex;justify-content:space-between;gap:12px;align-items:center}.account strong{overflow-wrap:anywhere}.ok{color:#67f7c7}.warn{color:#ffd77a}.bad{color:#ff8c9d}[hidden]{display:none!important}@media(max-width:480px){.actions{grid-template-columns:1fr}.account{display:block}.account span{display:block;margin-top:5px}}</style></head>
<body><main><header><h1>JARVIS OS</h1><p>BEZPIECZNY MOST TELEFONU</p></header><section class="card"><div class="account"><strong id="accountName">KONTO MICROSOFT</strong><span class="ok">SESJA AKTYWNA</span></div><p class="hint">Sesja wygasa po 60 minutach. Zwykłe ważne działania wymagają potwierdzenia na komputerze; wyłączenie ma osobne potwierdzenie właściciela poniżej.</p><div class="connection"><span id="connectionDot" class="dot"></span><strong id="connectionText">SPRAWDZAM KOMPUTER…</strong></div><label for="device">Urządzenie</label><input id="device" value="desktop-main" maxlength="64" autocapitalize="none"></section><section class="card"><div class="quick"><button type="button" data-command="status systemu">STATUS SYSTEMU</button><button type="button" data-command="status chmury">STATUS CHMURY</button></div><label for="command">Polecenie</label><textarea id="command" maxlength="4000" placeholder="Napisz, co JARVIS ma zrobić?"></textarea><button id="send" type="button">WYŚLIJ DO KOMPUTERA</button></section><section class="card"><h2>ZASILANIE KOMPUTERA</h2><p class="hint">Wyłączenie zatrzyma JARVIS, MT5 i obserwację PAPER. Po potwierdzeniu rozpocznie się 60 sekund odliczania.</p><div class="actions"><button id="powerOpen" class="danger" type="button">WYŁĄCZ KOMPUTER</button><button id="powerCancel" class="secondary" type="button">ANULUJ WYŁĄCZENIE</button></div><div id="powerConfirm" class="power-confirm" hidden><label for="powerPhrase">Aby potwierdzić, wpisz WYLACZ</label><input id="powerPhrase" maxlength="6" autocomplete="off" autocapitalize="characters"><div class="actions"><button id="powerSubmit" class="danger" type="button" disabled>POTWIERDZAM WYŁĄCZENIE</button><button id="powerBack" class="secondary" type="button">WRÓĆ</button></div></div></section><section class="card status" aria-live="polite"><span id="pill" class="pill">GOTOWY</span><div id="message">Wyślij pierwsze polecenie. Ostatni wynik wróci po odświeżeniu strony.</div></section><section class="card"><div class="actions"><button id="install" class="secondary" type="button" hidden>ZAINSTALUJ APLIKACJĘ</button><a class="button secondary" href="https://account.microsoft.com/security" target="_blank" rel="noopener">ZGUBIONY TELEFON</a><a class="button danger" href="/mobile-start">WYLOGUJ TEN TELEFON</a></div><p id="installHint" class="hint">Aby odebrać dostęp zgubionemu telefonowi, otwórz „Moje logowania” Microsoft i wyloguj jego sesję. Dostęp JARVIS OS i tak wygaśnie najpóźniej po godzinie.</p></section></main>
<script>(()=>{"use strict";const device=document.querySelector("#device"),command=document.querySelector("#command"),send=document.querySelector("#send"),pill=document.querySelector("#pill"),message=document.querySelector("#message"),connectionDot=document.querySelector("#connectionDot"),connectionText=document.querySelector("#connectionText"),accountName=document.querySelector("#accountName"),install=document.querySelector("#install"),installHint=document.querySelector("#installHint"),powerOpen=document.querySelector("#powerOpen"),powerCancel=document.querySelector("#powerCancel"),powerConfirm=document.querySelector("#powerConfirm"),powerPhrase=document.querySelector("#powerPhrase"),powerSubmit=document.querySelector("#powerSubmit"),powerBack=document.querySelector("#powerBack");let currentId="",pollTimer=0,probeId="",probeTimer=0,probeDeadline=0,installPrompt=null;const labels={queued:"W KOLEJCE",claimed:"ODEBRANE",waiting_local_confirmation:"CZEKA NA KOMPUTERZE",completed:"GOTOWE",failed:"NIEUDANE",cancelled:"ANULOWANE",expired:"WYGASŁO"},terminal=new Set(["completed","failed","cancelled","expired"]),lastKey="jarvisLastCommand";
function targetDevice(){const value=device.value.trim().toLowerCase();if(!/^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/.test(value))throw new Error("Nieprawidłowa nazwa urządzenia.");sessionStorage.setItem("jarvisPhoneDevice",value);return value}function show(state,text){pill.textContent=labels[state]||state.toUpperCase();pill.className="pill "+(state==="completed"?"ok":terminal.has(state)?"bad":state==="waiting_local_confirmation"?"warn":"");message.textContent=text||"Brak dodatkowych informacji."}function connection(state,text){connectionDot.className="dot "+state;connectionText.textContent=text}function setBusy(value){send.disabled=value;powerOpen.disabled=value;powerCancel.disabled=value}async function api(path,options){const response=await fetch(path,Object.assign({credentials:"same-origin"},options||{},{headers:Object.assign({Accept:"application/json"},options&&options.headers||{})})),data=await response.json().catch(()=>({}));if(response.status===401){location.replace("/phone");throw new Error("Sesja wygasła.")}if(!response.ok)throw new Error(data.message||data.error||"Połączenie nie powiodło się.");return data}function newRequestId(){const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return Array.from(bytes,value=>value.toString(16).padStart(2,"0")).join("")}async function requestIdFor(target,value){const input=new TextEncoder().encode(target+"\0"+value),digest=await crypto.subtle.digest("SHA-256",input),signature=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,"0")).join(""),key="jarvisPendingRequest";let stored={};try{stored=JSON.parse(sessionStorage.getItem(key)||"{}")}catch(_error){}if(!/^[a-f0-9]{32}$/.test(stored.id||"")||stored.signature!==signature){stored={id:newRequestId(),signature};sessionStorage.setItem(key,JSON.stringify(stored))}return stored.id}function clearPendingRequest(){sessionStorage.removeItem("jarvisPendingRequest")}function remember(id,target){sessionStorage.setItem(lastKey,JSON.stringify({id,device_id:target}))}function restoreReference(){try{const saved=JSON.parse(sessionStorage.getItem(lastKey)||"{}");if(/^[a-f0-9]{32}$/.test(saved.id||"")&&/^[a-z0-9-]{1,64}$/.test(saved.device_id||"")){currentId=saved.id;device.value=saved.device_id;return true}}catch(_error){}return false}async function refresh(){if(!currentId)return;try{const data=await api("/v1/remote/commands/"+encodeURIComponent(currentId)+"?device_id="+encodeURIComponent(targetDevice()));show(data.status,data.message);if(terminal.has(data.status)){clearInterval(pollTimer);setBusy(false)}}catch(error){show("failed",error.message);clearInterval(pollTimer);setBusy(false)}}async function submit(){const value=command.value.trim();if(!value)return show("failed","Wpisz polecenie.");let target;try{target=targetDevice()}catch(error){return show("failed",error.message)}setBusy(true);show("queued","Wysyłam polecenie…");try{const data=await api("/v1/remote/commands",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:target,command:value,request_id:await requestIdFor(target,value)})});clearPendingRequest();currentId=data.id;remember(data.id,target);show(data.status,data.message);clearInterval(pollTimer);pollTimer=setInterval(refresh,1500);refresh()}catch(error){show("failed",error.message+" Możesz bezpiecznie nacisnąć WYŚLIJ ponownie.");setBusy(false)}}async function submitPower(action){let target;try{target=targetDevice()}catch(error){return show("failed",error.message)}const confirmation=action==="shutdown"?powerPhrase.value.trim().toUpperCase():"";if(action==="shutdown"&&confirmation!=="WYLACZ")return show("failed","Wpisz dokładnie WYLACZ.");setBusy(true);show("queued",action==="shutdown"?"Przekazuję potwierdzone wyłączenie…":"Przekazuję anulowanie…");try{const signature="power:"+action+":"+confirmation,data=await api("/v1/remote/power",{method:"POST",headers:{"Content-Type":"application/json","X-JARVIS-POWER-CONTROL":"owner-v1"},body:JSON.stringify({device_id:target,action,confirmation,request_id:await requestIdFor(target,signature)})});clearPendingRequest();currentId=data.id;remember(data.id,target);powerPhrase.value="";powerSubmit.disabled=true;powerConfirm.hidden=true;show(data.status,data.message);clearInterval(pollTimer);pollTimer=setInterval(refresh,1500);refresh()}catch(error){show("failed",error.message);setBusy(false)}}async function checkProbe(){if(!probeId)return;try{const data=await api("/v1/remote/commands/"+encodeURIComponent(probeId)+"?device_id="+encodeURIComponent(targetDevice()));if(data.status==="completed"){connection("online","KOMPUTER ONLINE");probeId="";return}if(terminal.has(data.status)||Date.now()>probeDeadline){connection("offline","KOMPUTER NIE ODPOWIADA");probeId="";return}probeTimer=setTimeout(checkProbe,1000)}catch(_error){connection("offline","BRAK POŁĄCZENIA");probeId=""}}async function probe(){clearTimeout(probeTimer);probeId="";let target;try{target=targetDevice()}catch(error){connection("offline",error.message.toUpperCase());return}connection("checking","SPRAWDZAM KOMPUTER…");try{const data=await api("/v1/remote/probe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:target,request_id:newRequestId()})});probeId=data.id;probeDeadline=Date.now()+20000;probeTimer=setTimeout(checkProbe,500)}catch(_error){connection("offline","BRAK POŁĄCZENIA")}}async function loadIdentity(){try{const data=await api("/v1/phone/me");accountName.textContent=data.name||"KONTO MICROSOFT"}catch(_error){}}
window.addEventListener("beforeinstallprompt",event=>{event.preventDefault();installPrompt=event;install.hidden=false});install.addEventListener("click",async()=>{if(!installPrompt)return;installPrompt.prompt();const choice=await installPrompt.userChoice;installPrompt=null;install.hidden=true;installHint.textContent=choice.outcome==="accepted"?"JARVIS OS został dodany do telefonu.":"Możesz zainstalować aplikację później z menu przeglądarki."});window.addEventListener("appinstalled",()=>{install.hidden=true;installHint.textContent="JARVIS OS jest zainstalowany na tym telefonie."});document.querySelectorAll("[data-command]").forEach(button=>button.addEventListener("click",()=>{command.value=button.dataset.command}));send.addEventListener("click",submit);powerOpen.addEventListener("click",()=>{powerConfirm.hidden=false;powerPhrase.focus()});powerBack.addEventListener("click",()=>{powerConfirm.hidden=true;powerPhrase.value="";powerSubmit.disabled=true});powerPhrase.addEventListener("input",()=>{powerSubmit.disabled=powerPhrase.value.trim().toUpperCase()!=="WYLACZ"});powerSubmit.addEventListener("click",()=>submitPower("shutdown"));powerCancel.addEventListener("click",()=>submitPower("cancel_shutdown"));device.addEventListener("change",probe);device.value=sessionStorage.getItem("jarvisPhoneDevice")||device.value;if("serviceWorker" in navigator)navigator.serviceWorker.register("/phone-sw.js",{scope:"/phone"});loadIdentity();if(restoreReference())refresh();setTimeout(probe,250)})();</script></body></html>'''


def forex_status_page(
    snapshot: dict[str, object] | None,
    *,
    unavailable: bool = False,
) -> str:
    """Render the owner-only, script-free PAPER trading report."""

    selected = snapshot or {}
    performance_value = selected.get("v3_performance", {})
    performance = (
        performance_value if isinstance(performance_value, dict) else {}
    )
    positions_value = selected.get("v3_open_positions", [])
    positions = positions_value if isinstance(positions_value, list) else []
    pair_value = performance.get("pair_breakdown", {})
    pairs = pair_value if isinstance(pair_value, dict) else {}
    block_value = selected.get("observation_opening_blocks_by_pair", {})
    pair_blocks = block_value if isinstance(block_value, dict) else {}
    v3_reason_value = selected.get("v3_reason_codes_by_pair", {})
    v3_pair_reasons = (
        v3_reason_value if isinstance(v3_reason_value, dict) else {}
    )
    event_value = selected.get("activity_events", [])
    activity_events = event_value if isinstance(event_value, list) else []
    if selected.get("fresh") is not True:
        positions = []
        pairs = {}
        pair_blocks = {}
        v3_pair_reasons = {}

    def safe(value: object, fallback: str = "-") -> str:
        text = str(value if value not in (None, "") else fallback)
        return escape(text)

    def money(key: str) -> str:
        if selected.get("fresh") is not True:
            return "N/D"
        return safe(selected.get(key, "0")) + " PLN"

    def count(key: str, maximum: int = 1_000_000) -> int:
        if selected.get("fresh") is not True:
            return 0
        raw = selected.get(key, 0)
        if isinstance(raw, bool):
            return 0
        try:
            value = int(raw)
        except (TypeError, ValueError, OverflowError):
            return 0
        return value if 0 <= value <= maximum else 0

    if unavailable:
        state_class = "warn"
        state_label = "RAPORT JESZCZE NIEDOSTEPNY"
        state_message = (
            "Pierwszy bezpieczny raport pojawi sie po kolejnym cyklu PAPER."
        )
    elif selected.get("fresh") is True:
        state_class = "ok"
        state_label = "DANE AKTUALNE"
        state_message = "Ostatni cykl zakonczyl sie i raport jest aktualny."
    else:
        state_class = "warn"
        state_label = "DANE NIEAKTUALNE"
        state_message = "JARVIS zachowal ostatni raport, ale wymaga on odswiezenia."

    position_rows = "".join(
        "<tr><td>" + safe(item.get("pair")) + "</td><td>"
        + safe(item.get("side")) + "</td><td>"
        + safe(item.get("entry_price")) + "</td><td>"
        + safe(item.get("current_price")) + "</td><td>"
        + safe(item.get("stop_loss")) + "</td><td>"
        + safe(item.get("take_profit")) + "</td></tr>"
        for item in positions
        if isinstance(item, dict)
    ) or '<tr><td colspan="6">Brak otwartych pozycji PAPER.</td></tr>'
    pair_rows = "".join(
        "<tr><td>" + safe(pair) + "</td><td>"
        + safe(metrics.get("closed_trade_count", 0)) + "</td><td>"
        + safe(metrics.get("win_rate_pct", 0)) + "%</td><td>"
        + safe(metrics.get("net_realized_pnl_pln", 0)) + " PLN</td></tr>"
        for pair, metrics in sorted(pairs.items())
        if isinstance(metrics, dict)
    ) or '<tr><td colspan="4">Za malo danych do podzialu na pary.</td></tr>'
    block_labels = {
        "HIGH_IMPACT_EVENT_WINDOW": "okno waznego wydarzenia gospodarczego",
        "SECOND_SOURCE_UNAVAILABLE": "brak potwierdzenia z drugiego zrodla",
        "ECONOMIC_CALENDAR_UNAVAILABLE": "kalendarz gospodarczy niedostepny",
        "PLN_CONVERSION_UNAVAILABLE": "przelicznik PLN niedostepny",
        "MARKET_CLOSED": "rynek zamkniety",
    }
    block_rows = "".join(
        "<tr><td>" + safe(pair.replace("_", "/")) + "</td><td>"
        + safe(", ".join(
            block_labels.get(str(code), str(code))
            for code in codes
        )) + "</td></tr>"
        for pair, codes in sorted(pair_blocks.items())
        if isinstance(codes, list) and codes
    ) or '<tr><td colspan="2">Brak blokad par w ostatnim cyklu.</td></tr>'
    v3_reason_labels = {
        "NO_NEW_CROSSOVER": "brak nowego przeciecia srednich",
        "NO_ENTRY_SIGNAL": "brak bezpiecznego sygnalu wejscia",
        "BULLISH_CROSSOVER": "wzrostowe przeciecie srednich",
        "BEARISH_CROSSOVER": "spadkowe przeciecie srednich",
        "CANDIDATE_V3_SIGNAL_STRENGTH_TOO_LOW": (
            "sila sygnalu V3 jest zbyt mala"
        ),
        "CANDIDATE_V3_SIGNAL_STRENGTH_CONFIRMED": (
            "sila sygnalu V3 zostala potwierdzona"
        ),
        "CANDIDATE_V3_STRENGTH_HISTORY_INVALID": (
            "za malo poprawnej historii sily sygnalu"
        ),
        "SPREAD_TOO_WIDE": "spread jest zbyt szeroki",
        "STALE_CLOSED_BAR": "ostatnia zamknieta swieca jest nieaktualna",
        "MARKET_CLOSED": "rynek jest zamkniety",
    }
    v3_reason_rows = "".join(
        "<tr><td>" + safe(pair.replace("_", "/")) + "</td><td>"
        + safe(", ".join(
            v3_reason_labels.get(str(code), str(code))
            for code in codes
        )) + "</td></tr>"
        for pair, codes in sorted(v3_pair_reasons.items())
        if isinstance(codes, list) and codes
    ) or '<tr><td colspan="2">Brak powodow decyzji V3 w ostatnim cyklu.</td></tr>'
    event_kind_labels = {
        "DATA_BLOCKED": "DANE ZABLOKOWANE",
        "DATA_RECOVERED": "DANE PRZYWROCONE",
        "FOREX_PAPER_SAMPLE_REVIEW_READY": "PROBKA PAPER GOTOWA",
        "FOREX_V2_FORWARD_REVIEW_READY": "PROBKA V2 GOTOWA",
        "FOREX_V3_FORWARD_EVIDENCE_BLOCKED": "PROBKA V3 ZABLOKOWANA",
        "FOREX_V3_FORWARD_PROGRESS": "POSTEP V3",
        "FOREX_V3_SHADOW_FIRST_PLAN_RECORDED": "PIERWSZY PLAN V3",
        "FOREX_V3_SHADOW_INITIALIZED": "PORTFEL V3 UTWORZONY",
        "FOREX_V3_SHADOW_INITIALIZATION_READY": "PROBKA V3 GOTOWA",
        "FOREX_V3_SHADOW_PLAN_SAMPLE_READY": "PLANY V3 GOTOWE",
        "FOREX_V3_SHADOW_SIMULATION_ACTIVATED": "SYMULACJA V3 AKTYWNA",
        "POSITION_CLOSED": "POZYCJA PAPER ZAMKNIETA",
        "POSITION_OPENED": "POZYCJA PAPER OTWARTA",
        "POSITION_PROTECTION_ATTENTION": "OCHRONA POZYCJI — UWAGA",
        "POSITION_PROTECTION_RECOVERED": "OCHRONA POZYCJI PRZYWROCONA",
        "SAFETY_ATTENTION": "BEZPIECZENSTWO — UWAGA",
    }
    event_rows = "".join(
        "<tr><td>" + safe(
            str(item.get("occurred_at", "")).replace("T", " ")[:19]
        ) + "</td><td>" + safe(event_kind_labels.get(
            str(item.get("kind", "")).strip().upper(),
            "ZDARZENIE PAPER",
        )) + "</td><td>" + safe(item.get("message")) + "</td></tr>"
        for item in reversed(activity_events[-8:])
        if isinstance(item, dict)
    ) or '<tr><td colspan="3">Brak zapisanych zdarzen PAPER.</td></tr>'
    age_minutes = int(int(selected.get("age_seconds", 0) or 0) / 60)

    runtime_code = str(selected.get("runtime_decision", "")).strip().upper()
    runtime_label = {
        "NO_ENTRY_SIGNAL": "Brak bezpiecznego sygnalu wejscia",
        "PAPER_EXECUTED": "Wykonano symulacje PAPER",
        "PAIR_DATA_BLOCKED": "Czesc par zablokowana przez dane",
        "DATA_BLOCKED": "Cykl zablokowany przez dane",
    }.get(runtime_code, runtime_code or "Brak wyniku")
    ready_pairs = count("runtime_ready_pair_count", 7)
    blocked_pairs = count("runtime_blocked_pair_count", 7)
    execution_count = count("runtime_execution_count", 20)

    accepted_cycles = count("v3_forward_accepted_cycle_count")
    required_cycles = count("v3_forward_minimum_cycle_count")
    accepted_days = count("v3_forward_accepted_market_day_count")
    required_days = count("v3_forward_minimum_market_day_count")
    remaining_cycles = max(required_cycles - accepted_cycles, 0)
    remaining_days = max(required_days - accepted_days, 0)
    cycle_progress_max = max(required_cycles, 1)
    day_progress_max = max(required_days, 1)
    evidence_code = str(
        selected.get("v3_forward_status", "")
    ).strip().upper()
    evidence_complete = selected.get("v3_forward_sample_complete") is True
    evidence_valid = (
        selected.get("v3_forward_source_state_valid") is True
        and count("v3_forward_invalid_cycle_count") == 0
    )
    evidence_reason_code = str(
        selected.get("v3_activation_reason", "")
        or selected.get("v3_plan_reason", "")
    ).strip().upper()
    evidence_reason_labels = {
        "V3_FORWARD_EVIDENCE_INCOMPLETE": (
            "Trwa zbieranie niezaleznej probki V3."
        ),
        "WAITING_FOR_FORWARD_SAMPLE": (
            "Plan V3 czeka na ukonczenie wymaganej probki."
        ),
        "STATUS_UNAVAILABLE": "Status V3 jest chwilowo niedostepny.",
    }
    if selected.get("fresh") is not True:
        evidence_class = "warn"
        evidence_label = "Postep niedostepny do czasu swiezego raportu"
        evidence_detail = "Najpierw potrzebny jest nowy poprawny cykl PAPER."
    elif evidence_complete and evidence_valid:
        evidence_class = "ok"
        evidence_label = "Probka gotowa do recznego przegladu"
        evidence_detail = "Wszystkie wymagania probki V3 zostaly spelnione."
    elif evidence_valid and evidence_code == "COLLECTING_FORWARD_EVIDENCE":
        evidence_class = "warn"
        evidence_label = "JARVIS nadal zbiera niezalezne obserwacje"
        evidence_detail = (
            evidence_reason_labels.get(
                evidence_reason_code,
                "Probka V3 nie jest jeszcze kompletna.",
            )
            + f" Pozostalo {remaining_cycles} cykli i "
            + f"{remaining_days} dni rynkowych."
        )
    else:
        evidence_class = "bad"
        evidence_label = "Dowody sa zablokowane lub niespojne"
        evidence_detail = evidence_reason_labels.get(
            evidence_reason_code,
            "Raport wymaga kontroli przed kolejnym etapem V3.",
        )

    activation_code = str(
        selected.get("v3_activation_status", "")
    ).strip().upper()
    initialization_code = str(
        selected.get("v3_initialization_status", "")
    ).strip().upper()
    plan_observation_code = str(
        selected.get("v3_plan_observation_status", "")
    ).strip().upper()
    simulation_code = str(selected.get("v3_status", "")).strip().upper()
    shadow_active = activation_code in {
        "ALREADY_ACTIVE",
        "SIMULATION_ACTIVATED",
    }
    shadow_initialized = shadow_active or initialization_code in {
        "INITIALIZED_SHADOW_INACTIVE",
        "ALREADY_INITIALIZED_SHADOW_INACTIVE",
    }

    if selected.get("fresh") is not True:
        gate_values = [
            ("DOWODY FORWARD", "NIEDOSTEPNE", "warn", "Czeka na swiezy raport Azure."),
            ("PORTFEL SHADOW", "NIEDOSTEPNY", "warn", "Stan jest ukryty do czasu swiezego raportu."),
            ("PLANY SHADOW", "NIEDOSTEPNE", "warn", "Stan jest ukryty do czasu swiezego raportu."),
            ("SYMULACJA V3", "NIEDOSTEPNA", "warn", "Stan jest ukryty do czasu swiezego raportu."),
        ]
    else:
        if evidence_complete and evidence_valid:
            forward_gate = (
                "GOTOWE",
                "ok",
                "Probka spelnila wymagania liczby cykli, dni i spojnosci.",
            )
        elif evidence_valid and evidence_code == "COLLECTING_FORWARD_EVIDENCE":
            forward_gate = (
                "W TOKU",
                "warn",
                f"Pozostalo {remaining_cycles} cykli i {remaining_days} dni rynkowych.",
            )
        else:
            forward_gate = (
                "ZABLOKOWANE",
                "bad",
                "Dowody wymagaja poprawnego cyklu lub kontroli spojnosci.",
            )

        if shadow_active:
            shadow_gate = (
                "AKTYWNY PAPER",
                "ok",
                "Izolowany portfel istnieje i nie ma dostepu do brokera.",
            )
        elif shadow_initialized:
            shadow_gate = (
                "ZAINICJALIZOWANY",
                "ok",
                "Izolowany portfel istnieje, ale nie wykonuje prawdziwych zlecen.",
            )
        elif evidence_complete and evidence_valid:
            shadow_gate = (
                "GOTOWY DO KONTROLOWANEGO STARTU",
                "warn",
                "Wymaga oddzielnej bezpiecznej inicjalizacji SHADOW.",
            )
        else:
            shadow_gate = (
                "CZEKA NA PROBKE",
                "warn" if evidence_valid else "bad",
                "Nie powstanie przed poprawna, kompletna probka forward.",
            )

        if shadow_active:
            plan_gate = (
                "PROBKA PLANOW ZAKONCZONA",
                "ok",
                "Wczesniejszy przeglad planow dopuscil izolowana symulacje.",
            )
        elif plan_observation_code in {
            "SHADOW_PLAN_OBSERVED",
            "SHADOW_PLAN_ALREADY_OBSERVED",
        }:
            plan_gate = (
                "ZBIERANIE PLANOW",
                "warn",
                "JARVIS zapisuje nieuruchamialne plany do osobnego dziennika.",
            )
        elif "BLOCKED" in plan_observation_code:
            plan_gate = (
                "ZABLOKOWANE",
                "bad",
                "Dziennik planow lub biezaca obserwacja wymaga kontroli.",
            )
        elif evidence_complete and evidence_valid:
            plan_gate = (
                "CZEKA NA PORTFEL SHADOW",
                "warn",
                "Plany rusza dopiero po bezpiecznej inicjalizacji portfela.",
            )
        else:
            plan_gate = (
                "CZEKA NA PROBKE",
                "warn",
                "Najpierw musi zakonczyc sie bramka dowodow forward.",
            )

        if shadow_active or simulation_code == "SHADOW_SIMULATION_CYCLE_COMPLETED":
            simulation_gate = (
                "AKTYWNA - TYLKO PAPER",
                "ok",
                "Wyniki powstaja wyłącznie w izolowanym portfelu symulacyjnym.",
            )
        elif "BLOCKED" in simulation_code:
            simulation_gate = (
                "ZABLOKOWANA",
                "bad",
                "Symulacja zatrzymala sie bez wysylania zlecen do brokera.",
            )
        else:
            simulation_gate = (
                "CZEKA NA DOWODY I PLANY",
                "warn",
                "Nie uruchomi sie przed przejsciem osobnych bramek PAPER.",
            )

        gate_values = [
            ("DOWODY FORWARD", *forward_gate),
            ("PORTFEL SHADOW", *shadow_gate),
            ("PLANY SHADOW", *plan_gate),
            ("SYMULACJA V3", *simulation_gate),
        ]

    gate_values.append((
        "LIVE",
        "ZAWSZE ZABLOKOWANE",
        "bad",
        "Zadna bramka PAPER nie wlacza prawdziwych zlecen automatycznie.",
    ))
    gate_rows = "".join(
        '<div class="gate"><span class="gate-number">'
        + str(index)
        + '</span><div><strong>'
        + safe(title)
        + '</strong><span class="state '
        + safe(css_class)
        + '">'
        + safe(label)
        + '</span><p>'
        + safe(detail)
        + '</p></div></div>'
        for index, (title, label, css_class, detail) in enumerate(
            gate_values,
            start=1,
        )
    )

    return f'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#03121f"><title>JARVIS OS &mdash; Trading PAPER</title><style>:root{{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:#020b13;color:#dff7ff}}main{{width:min(980px,100%);margin:auto;padding:20px}}header,.card{{border:1px solid #176d88;border-radius:18px;background:#03131f;padding:18px;margin:12px 0}}h1{{margin:0 0 8px;letter-spacing:.12em}}h2{{font-size:16px;letter-spacing:.08em}}.paper{{display:inline-block;padding:7px 12px;border:1px solid #67f7c7;border-radius:999px;color:#67f7c7;font-weight:800}}.state{{display:block;font-weight:800;margin-top:4px}}.ok{{color:#67f7c7}}.warn{{color:#ffd77a}}.bad{{color:#ff8c9d}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.metric{{border:1px solid #174b60;border-radius:12px;padding:12px}}.metric span{{display:block;color:#83d5ed;font-size:12px;margin-bottom:6px}}.gates{{display:grid;gap:10px}}.gate{{display:grid;grid-template-columns:34px 1fr;gap:12px;border:1px solid #174b60;border-radius:12px;padding:12px}}.gate-number{{display:grid;place-items:center;width:30px;height:30px;border:1px solid #31cce9;border-radius:50%;color:#83d5ed;font-weight:800}}.gate p{{margin:6px 0 0}}progress{{width:100%;height:12px;accent-color:#31cce9;margin-top:8px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px 8px;border-bottom:1px solid #174b60;text-align:left}}.scroll{{overflow-x:auto}}p{{color:#a5c8d3;line-height:1.5}}.note{{font-size:13px}}a{{display:block;text-align:center;border:1px solid #31cce9;border-radius:12px;padding:13px;color:#fff;background:#0b4866;text-decoration:none;font-weight:700}}</style></head><body><main><header><span class="paper">WYLACZNIE PAPER &mdash; ZERO PRAWDZIWYCH ZLECEN</span><h1>TRADING JARVIS OS</h1><p class="state {state_class}">{state_label}</p><p>{state_message}</p><p>Cykl: {safe(selected.get("cycle_id"))}<br>Odczyt: {safe(selected.get("observed_at"))} &middot; wiek: {age_minutes} min</p></header><section class="card"><h2>BIEZACY CYKL</h2><div class="grid"><div class="metric"><span>Decyzja</span>{safe(runtime_label)}</div><div class="metric"><span>Pary gotowe</span>{ready_pairs} / 7</div><div class="metric"><span>Pary zablokowane</span>{blocked_pairs}</div><div class="metric"><span>Wykonania PAPER</span>{execution_count}</div></div></section><section class="card"><h2>BRAMKI V3 &mdash; CO DALEJ</h2><div class="gates">{gate_rows}</div><p class="note">Bramki sa niezalezne: istniejaca izolowana symulacja moze dzialac, gdy JARVIS zbiera nowa probke. Zadna z nich nie daje dostepu do prawdziwych pieniedzy.</p></section><section class="card"><h2>DLACZEGO PARA BYLA ZABLOKOWANA</h2><div class="scroll"><table><thead><tr><th>Para</th><th>Powod</th></tr></thead><tbody>{block_rows}</tbody></table></div><p class="note">To bezpieczne kody kontroli danych. Panel nie pokazuje kluczy API, surowych cen ani instrukcji wykonawczych.</p></section><section class="card"><h2>DLACZEGO V3 PODJAL TAKA DECYZJE</h2><div class="scroll"><table><thead><tr><th>Para</th><th>Powod</th></tr></thead><tbody>{v3_reason_rows}</tbody></table></div><p class="note">Powody opisuja ostatnia ocene strategii PAPER. Nie sa rekomendacja inwestycyjna ani instrukcja otwarcia zlecenia.</p></section><section class="card"><h2>POSTEP PROBKI V3</h2><p class="state {evidence_class}">{evidence_label}</p><p>{safe(evidence_detail)}</p><div class="grid"><div class="metric"><span>Unikalne cykle</span>{accepted_cycles} / {required_cycles}<progress value="{min(accepted_cycles, cycle_progress_max)}" max="{cycle_progress_max}"></progress></div><div class="metric"><span>Dni rynkowe</span>{accepted_days} / {required_days}<progress value="{min(accepted_days, day_progress_max)}" max="{day_progress_max}"></progress></div><div class="metric"><span>Pozostalo cykli</span>{remaining_cycles}</div><div class="metric"><span>Pozostalo dni rynkowych</span>{remaining_days}</div></div><p class="note">Ten prog sprawdza ciaglosc i liczbe obserwacji. Nie potwierdza zysku, nie zmienia strategii i nigdy automatycznie nie wlacza LIVE.</p></section><section class="card"><h2>OSTATNIE ZDARZENIA PAPER</h2><div class="scroll"><table><thead><tr><th>Czas UTC</th><th>Typ</th><th>Wiadomosc</th></tr></thead><tbody>{event_rows}</tbody></table></div><p class="note">Historia jest przechowywana w Azure i pozostaje dostepna na telefonie takze wtedy, gdy komputer jest wylaczony.</p></section><section class="card"><h2>WYNIK V3</h2><div class="grid"><div class="metric"><span>Saldo</span>{money("v3_balance_pln")}</div><div class="metric"><span>Kapital z pozycjami</span>{money("v3_equity_pln")}</div><div class="metric"><span>Wynik zamkniety</span>{money("v3_realized_pnl_pln")}</div><div class="metric"><span>Wynik otwarty</span>{money("v3_unrealized_pnl_pln")}</div><div class="metric"><span>Zamkniete transakcje</span>{safe(selected.get("v3_closed_trade_count", 0))}</div><div class="metric"><span>Skutecznosc</span>{safe(selected.get("v3_win_rate_pct", 0))}%</div><div class="metric"><span>Profit factor</span>{safe(performance.get("profit_factor"), "brak")}</div><div class="metric"><span>Maks. obsuniecie</span>{safe(performance.get("maximum_closed_trade_drawdown_pln", 0))} PLN</div></div></section><section class="card"><h2>OTWARTE POZYCJE PAPER</h2><div class="scroll"><table><thead><tr><th>Para</th><th>Kierunek</th><th>Wejscie</th><th>Teraz</th><th>SL</th><th>TP</th></tr></thead><tbody>{position_rows}</tbody></table></div></section><section class="card"><h2>WYNIKI WEDLUG PAR</h2><div class="scroll"><table><thead><tr><th>Para</th><th>Transakcje</th><th>Skutecznosc</th><th>Wynik</th></tr></thead><tbody>{pair_rows}</tbody></table></div></section><a href="/phone">WROC DO PANELU TELEFONU</a></main></body></html>'''
