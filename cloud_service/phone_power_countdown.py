from __future__ import annotations

from cloud_service.phone_ui import PHONE_PAGE as BASE_PHONE_PAGE


_POWER_COUNTDOWN_CSS = (
    ".power-countdown{margin:12px 0;border:1px solid #8a5360;border-radius:12px;"
    "padding:12px;text-align:center;font-weight:800;letter-spacing:.08em;"
    "background:#271018}.power-countdown.warn{color:#ffd77a;box-shadow:0 0 18px "
    "#ffd77a18}.power-countdown.bad{color:#ff9cad}"
)
_POWER_COUNTDOWN_HTML = (
    '<div id="powerCountdown" class="power-countdown" hidden '
    'aria-live="assertive"></div>'
)
_POWER_COUNTDOWN_SCRIPT = r'''const powerDeadlineKey="jarvisPowerDeadline";
function clearPowerCountdown(){clearTimeout(powerTimer);powerTimer=0;sessionStorage.removeItem(powerDeadlineKey);powerCountdown.hidden=true;powerCountdown.textContent=""}
function renderPowerCountdown(){clearTimeout(powerTimer);powerTimer=0;const deadline=Number(sessionStorage.getItem(powerDeadlineKey)||0);if(!Number.isFinite(deadline)||deadline<=0){powerCountdown.hidden=true;return}const remaining=Math.max(0,Math.ceil((deadline-Date.now())/1000));powerCountdown.hidden=false;if(remaining<=0){sessionStorage.removeItem(powerDeadlineKey);powerCountdown.className="power-countdown bad";powerCountdown.textContent="CZAS ODLICZANIA MINAL - KOMPUTER MOZE CZEKAC NA ZAMKNIECIE APLIKACJI";return}powerCountdown.className="power-countdown warn";powerCountdown.textContent="WYLACZENIE ZA "+remaining+" S";powerTimer=setTimeout(renderPowerCountdown,250)}
function startPowerCountdown(updatedAt){const reportedAt=Number(updatedAt)*1000,startedAt=Number.isFinite(reportedAt)&&reportedAt>0?reportedAt:Date.now();sessionStorage.setItem(powerDeadlineKey,String(startedAt+60000));renderPowerCountdown()}
function syncPowerCountdown(data){if(!data||data.status!=="completed")return;if(data.kind==="power_shutdown")startPowerCountdown(data.updated_at);else if(data.kind==="power_cancel")clearPowerCountdown()}
function restorePowerCountdown(){renderPowerCountdown()}
'''


def enhance_phone_page(page: str) -> str:
    """Add a recoverable visual countdown without changing power authority."""

    result = str(page)
    replacements = (
        ("</style></head>", _POWER_COUNTDOWN_CSS + "</style></head>"),
        (
            '<div class="actions"><button id="powerOpen"',
            _POWER_COUNTDOWN_HTML
            + '<div class="actions"><button id="powerOpen"',
        ),
        (
            'powerBack=document.querySelector("#powerBack");let currentId=',
            'powerBack=document.querySelector("#powerBack"),'
            'powerCountdown=document.querySelector("#powerCountdown");'
            'let powerTimer=0,currentId=',
        ),
        ("function targetDevice()", _POWER_COUNTDOWN_SCRIPT + "function targetDevice()"),
        (
            "show(data.status,data.message);if(terminal.has(data.status))",
            "show(data.status,data.message);syncPowerCountdown(data);"
            "if(terminal.has(data.status))",
        ),
        (
            "loadIdentity();if(restoreReference())refresh();setTimeout(probe,250)",
            "loadIdentity();restorePowerCountdown();"
            "if(restoreReference())refresh();setTimeout(probe,250)",
        ),
    )
    for anchor, replacement in replacements:
        if result.count(anchor) != 1:
            raise RuntimeError("phone power countdown template anchor changed")
        result = result.replace(anchor, replacement, 1)
    return result


PHONE_PAGE = enhance_phone_page(BASE_PHONE_PAGE)


__all__ = ["PHONE_PAGE", "enhance_phone_page"]
