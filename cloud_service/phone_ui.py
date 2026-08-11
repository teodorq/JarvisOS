from __future__ import annotations

PHONE_PAGE = r"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#03121f">
<title>JARVIS OS &mdash; telefon</title>
<style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;min-height:100vh;color:#dff7ff;background:radial-gradient(circle at 50% -10%,#08385a,#020b13 55%)}main{width:min(720px,100%);margin:auto;padding:28px 18px 44px}header{text-align:center;margin-bottom:24px}h1{margin:0;letter-spacing:.22em;font-size:clamp(25px,7vw,40px)}header p{color:#73cdea;margin:8px 0 0;letter-spacing:.08em}.card{background:#03131fe8;border:1px solid #0e6281;border-radius:18px;padding:18px;box-shadow:0 14px 50px #0009;margin:14px 0}label{display:block;color:#83d5ed;font-size:13px;margin:12px 0 6px}input,textarea,button{width:100%;border-radius:12px;font:inherit}input,textarea{color:#eaffff;background:#010b13;border:1px solid #175f78;padding:13px;outline:none}input:focus,textarea:focus{border-color:#3edbff;box-shadow:0 0 0 3px #1cc8ed22}textarea{min-height:104px;resize:vertical}button{border:1px solid #31cce9;background:linear-gradient(135deg,#0c7898,#0b4866);color:white;padding:13px 16px;font-weight:700;cursor:pointer}button:disabled{opacity:.55;cursor:wait}.quick{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:10px 0 14px}.quick button{background:#082739;font-weight:600;padding:10px}.connection{display:flex;align-items:center;gap:9px;border:1px solid #174b60;border-radius:12px;padding:10px 12px;margin-bottom:12px;color:#91bbca;font-size:13px;letter-spacing:.05em}.dot{width:10px;height:10px;border-radius:50%;background:#70838b;box-shadow:0 0 0 4px #70838b18}.dot.checking{background:#ffd77a;box-shadow:0 0 12px #ffd77a}.dot.online{background:#67f7c7;box-shadow:0 0 12px #67f7c7}.dot.offline{background:#ff8c9d;box-shadow:0 0 12px #ff8c9d}.status{min-height:96px;display:grid;align-content:center;text-align:center}.pill{display:inline-block;justify-self:center;padding:6px 12px;border-radius:999px;border:1px solid #176d88;color:#84def4;margin-bottom:10px}#message{white-space:pre-wrap;line-height:1.5}.hint{color:#7aa5b6;font-size:12px;line-height:1.45}.ok{color:#67f7c7}.warn{color:#ffd77a}.bad{color:#ff8c9d}
</style>
</head>
<body><main>
<header><h1>JARVIS OS</h1><p>BEZPIECZNY MOST TELEFONU</p></header>
<section class="card">
<div class="connection"><span id="connectionDot" class="dot"></span><strong id="connectionText">WPROWADŹ KOD PAROWANIA</strong></div>
<label for="token">Kod parowania</label><input id="token" type="password" autocomplete="off" placeholder="Wklej prywatny kod">
<label for="device">Urządzenie</label><input id="device" value="desktop-main" maxlength="64" autocapitalize="none">
<p class="hint">Kod pozostaje tylko w tej karcie. Ważne działania nadal wymagają potwierdzenia na komputerze.</p>
</section>
<section class="card">
<div class="quick"><button type="button" data-command="status systemu">STATUS SYSTEMU</button><button type="button" data-command="status chmury">STATUS CHMURY</button></div>
<label for="command">Polecenie</label><textarea id="command" maxlength="4000" placeholder="Napisz, co JARVIS ma zrobić?"></textarea>
<button id="send" type="button">WYŚLIJ DO KOMPUTERA</button>
</section>
<section class="card status" aria-live="polite"><span id="pill" class="pill">GOTOWY</span><div id="message">Połącz telefon kodem parowania i wyślij pierwsze polecenie.</div></section>
</main>
<script>
(()=>{"use strict";
const token=document.querySelector("#token"),device=document.querySelector("#device"),command=document.querySelector("#command"),send=document.querySelector("#send"),pill=document.querySelector("#pill"),message=document.querySelector("#message"),connectionDot=document.querySelector("#connectionDot"),connectionText=document.querySelector("#connectionText");
let currentId="",pollTimer=0,probeId="",probeTimer=0,probeDeadline=0;
const labels={queued:"W KOLEJCE",claimed:"ODEBRANE",waiting_local_confirmation:"CZEKA NA KOMPUTERZE",completed:"GOTOWE",failed:"NIEUDANE",cancelled:"ANULOWANE",expired:"WYGASŁO"},terminal=new Set(["completed","failed","cancelled","expired"]),fragment=new URLSearchParams(location.hash.slice(1));
if(fragment.get("token")){sessionStorage.setItem("jarvisPhoneToken",fragment.get("token"));token.value=fragment.get("token")}else token.value=sessionStorage.getItem("jarvisPhoneToken")||"";
if(fragment.get("device"))device.value=fragment.get("device");
if(location.hash)history.replaceState(null,"",location.pathname+location.search);
function authToken(){const value=token.value.trim();if(value)sessionStorage.setItem("jarvisPhoneToken",value);return value}
function targetDevice(){const value=device.value.trim().toLowerCase();if(!/^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/.test(value))throw new Error("Nieprawidłowa nazwa urządzenia.");return value}
function show(state,text){pill.textContent=labels[state]||state.toUpperCase();pill.className="pill "+(state==="completed"?"ok":terminal.has(state)?"bad":state==="waiting_local_confirmation"?"warn":"");message.textContent=text||"Brak dodatkowych informacji."}
function connection(state,text){connectionDot.className="dot "+state;connectionText.textContent=text}
async function api(path,options){const secret=authToken();if(!secret)throw new Error("Wpisz kod parowania.");const response=await fetch(path,Object.assign({},options||{},{headers:Object.assign({Authorization:"Bearer "+secret,Accept:"application/json"},options&&options.headers||{})})),data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.message||data.error||"Połączenie nie powiodło się.");return data}
async function refresh(){if(!currentId)return;try{const data=await api("/v1/remote/commands/"+encodeURIComponent(currentId)+"?device_id="+encodeURIComponent(targetDevice()));show(data.status,data.message);if(terminal.has(data.status)){currentId="";clearInterval(pollTimer);send.disabled=false}}catch(error){show("failed",error.message);clearInterval(pollTimer);send.disabled=false}}
async function submit(){const value=command.value.trim();if(!value)return show("failed","Wpisz polecenie.");let target;try{target=targetDevice()}catch(error){return show("failed",error.message)}send.disabled=true;show("queued","Wysyłam polecenie…");try{const data=await api("/v1/remote/commands",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:target,command:value})});currentId=data.id;show(data.status,data.message);clearInterval(pollTimer);pollTimer=setInterval(refresh,1500);refresh()}catch(error){show("failed",error.message);send.disabled=false}}
async function checkProbe(){if(!probeId)return;try{const data=await api("/v1/remote/commands/"+encodeURIComponent(probeId)+"?device_id="+encodeURIComponent(targetDevice()));if(data.status==="completed"){connection("online","KOMPUTER ONLINE");probeId="";return}if(terminal.has(data.status)||Date.now()>probeDeadline){connection("offline","KOMPUTER NIE ODPOWIADA");probeId="";return}probeTimer=setTimeout(checkProbe,1000)}catch(_error){connection("offline","BRAK POŁĄCZENIA");probeId=""}}
async function probe(){clearTimeout(probeTimer);probeId="";if(!authToken()){connection("","WPROWADŹ KOD PAROWANIA");return}let target;try{target=targetDevice()}catch(error){connection("offline",error.message.toUpperCase());return}connection("checking","SPRAWDZAM KOMPUTER…");try{const data=await api("/v1/remote/probe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:target})});probeId=data.id;probeDeadline=Date.now()+20000;probeTimer=setTimeout(checkProbe,500)}catch(_error){connection("offline","BRAK POŁĄCZENIA")}}
document.querySelectorAll("[data-command]").forEach(button=>button.addEventListener("click",()=>{command.value=button.dataset.command}));
send.addEventListener("click",submit);token.addEventListener("change",probe);device.addEventListener("change",probe);if(token.value)setTimeout(probe,250);
})();
</script>
</body></html>"""