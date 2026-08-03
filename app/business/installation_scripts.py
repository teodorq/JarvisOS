from __future__ import annotations


START_SCRIPT = r'''@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" pythonw.exe main.py
)
exit /b 0
'''


def install_cmd() -> str:
    return r'''@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "TARGET=%SystemDrive%\JarvisAI"
if not "%~1"=="" set "TARGET=%~1"
echo ============================================================
echo JARVIS OS RC1 - INSTALACJA
ECHO Cel: %TARGET%
echo ============================================================
echo Kod projektu jest lokalny. Instalacja bibliotek Python moze
ECHO wymagac dostepu do skonfigurowanego zrodla pip.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_JARVIS_OS_BUSINESS.ps1" -PackageRoot "%~dp0" -InstallRoot "%TARGET%"
if errorlevel 1 (
    echo.
    echo Instalacja nie powiodla sie. Zmiany zostaly wycofane.
    pause
    exit /b 1
)
echo.
echo JARVIS OS RC1 zainstalowany poprawnie.
pause
'''


def install_ps1() -> str:
    return r'''param(
  [Parameter(Mandatory=$true)][string]$PackageRoot,
  [Parameter(Mandatory=$true)][string]$InstallRoot,
  [switch]$SkipDependencies
)
$ErrorActionPreference='Stop'
$package=(Resolve-Path -LiteralPath $PackageRoot).Path
$payload=Join-Path $package 'PAYLOAD'
$manifestPath=Join-Path $package 'JARVIS_BUSINESS_SETUP_MANIFEST.json'
if(-not (Test-Path -LiteralPath $payload -PathType Container)){throw 'Brak katalogu PAYLOAD.'}
if(-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'Brak manifestu instalacyjnego.'}
$manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($manifest.type -ne 'JARVIS_BUSINESS_SETUP'){throw 'Nieprawidlowy typ pakietu.'}
$target=[IO.Path]::GetFullPath($InstallRoot)
$created=$false
if(Test-Path -LiteralPath $target){
  $existing=@(Get-ChildItem -LiteralPath $target -Force -ErrorAction SilentlyContinue)
  if($existing.Count -gt 0){throw ('Katalog docelowy nie jest pusty: '+$target)}
  $created=$true
}else{
  New-Item -ItemType Directory -Force -Path $target|Out-Null
  $created=$true
}
try{
  foreach($property in $manifest.files.PSObject.Properties){
    $relative=[string]$property.Name
    if([IO.Path]::IsPathRooted($relative) -or $relative -match '(^|[\\/])\.\.([\\/]|$)'){throw ('Niebezpieczna sciezka: '+$relative)}
    $source=Join-Path $payload $relative
    if(-not (Test-Path -LiteralPath $source -PathType Leaf)){throw ('Brak pliku: '+$relative)}
    $actual=(Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
    if($actual -ne ([string]$property.Value).ToLowerInvariant()){throw ('Niezgodny SHA-256: '+$relative)}
  }
  Get-ChildItem -LiteralPath $payload -Recurse -File | ForEach-Object{
    $relative=$_.FullName.Substring($payload.Length).TrimStart('\\','/')
    $destination=Join-Path $target $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent)|Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
  }
  Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $target 'JARVIS_BUSINESS_SETUP_MANIFEST.json') -Force
  Set-Content -LiteralPath (Join-Path $target 'start_jarvis.bat') -Value @'
@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" pythonw.exe main.py
)
exit /b 0
'@ -Encoding ASCII
  $python=(Get-Command py -ErrorAction SilentlyContinue)
  if($python){& py -3 -m venv (Join-Path $target '.venv')}
  else{& python -m venv (Join-Path $target '.venv')}
  if($LASTEXITCODE -ne 0){throw 'Nie udalo sie utworzyc srodowiska .venv.'}
  $venvPython=Join-Path $target '.venv\Scripts\python.exe'
  if(-not $SkipDependencies){
    & $venvPython -m pip install --upgrade pip
    if($LASTEXITCODE -ne 0){throw 'Aktualizacja pip nie powiodla sie.'}
    & $venvPython -m pip install -r (Join-Path $target 'requirements.txt')
    if($LASTEXITCODE -ne 0){throw 'Instalacja bibliotek nie powiodla sie.'}
  }
  Push-Location $target
  & $venvPython -m compileall -q app tests
  if($LASTEXITCODE -ne 0){throw 'Kontrola skladni nie przeszla.'}
  & $venvPython -m unittest discover -s tests -p 'test_*.py'
  if($LASTEXITCODE -ne 0){throw 'Testy instalacji nie przeszly.'}
  & $venvPython -c "from app.business.installation_manager import BusinessInstallationManager; from pathlib import Path; result=BusinessInstallationManager(Path.cwd()).initialize_first_run(); raise SystemExit(0 if result.get('success') else 1)"
  if($LASTEXITCODE -ne 0){throw 'Pierwsze uruchomienie nie zostalo przygotowane.'}
  Pop-Location
  & (Join-Path $package 'CREATE_DESKTOP_SHORTCUT.ps1') -InstallRoot $target
  if($LASTEXITCODE -ne 0){throw 'Nie udalo sie utworzyc skrotu.'}
  Copy-Item -LiteralPath (Join-Path $package 'UNINSTALL_JARVIS_OS_BUSINESS.cmd') -Destination (Join-Path $target 'UNINSTALL_JARVIS_OS_BUSINESS.cmd') -Force
  Copy-Item -LiteralPath (Join-Path $package 'UNINSTALL_JARVIS_OS_BUSINESS.ps1') -Destination (Join-Path $target 'UNINSTALL_JARVIS_OS_BUSINESS.ps1') -Force
}catch{
  if((Get-Location).Path -eq $target){Pop-Location}
  if($created -and (Test-Path -LiteralPath $target)){Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue}
  throw
}
'''


def shortcut_ps1() -> str:
    return r'''param([Parameter(Mandatory=$true)][string]$InstallRoot)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($InstallRoot)
$launcher=Join-Path $root 'start_jarvis.bat'
if(-not (Test-Path -LiteralPath $launcher -PathType Leaf)){throw 'Brak start_jarvis.bat.'}
$desktop=[Environment]::GetFolderPath('Desktop')
$link=Join-Path $desktop 'JARVIS OS.lnk'
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($link)
$shortcut.TargetPath=$launcher
$shortcut.WorkingDirectory=$root
$icon=Join-Path $root 'JARVIS_OS.ico'
if(Test-Path -LiteralPath $icon){$shortcut.IconLocation=$icon}
$shortcut.Description='JARVIS OS RC1'
$shortcut.Save()
Write-Host ('Skrot utworzony: '+$link)
'''


def uninstall_cmd() -> str:
    return r'''@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ============================================================
echo JARVIS OS - BEZPIECZNA DEINSTALACJA
echo ============================================================
echo Przed usunieciem zostanie wykonany backup konfiguracji i danych.
set /p "CONFIRM=Wpisz USUN, aby kontynuowac: "
if /I not "%CONFIRM%"=="USUN" (
    echo Anulowano.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0UNINSTALL_JARVIS_OS_BUSINESS.ps1" -InstallRoot "%~dp0"
if errorlevel 1 (
    echo Deinstalacja nie powiodla sie.
    pause
    exit /b 1
)
echo Deinstalacja zakonczona. Backup pozostawiono w Dokumentach.
exit /b 0
'''


def uninstall_ps1() -> str:
    return r'''param([Parameter(Mandatory=$true)][string]$InstallRoot)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($InstallRoot).TrimEnd('\\')
if(-not (Test-Path -LiteralPath (Join-Path $root 'main.py'))){throw 'To nie wyglada na katalog JARVIS OS.'}
$stamp=Get-Date -Format yyyyMMdd_HHmmss
$documents=[Environment]::GetFolderPath('MyDocuments')
$backup=Join-Path $documents ('JARVIS_OS_BUSINESS_USER_DATA_'+$stamp+'.zip')
$work=Join-Path $env:TEMP ('JARVIS_UNINSTALL_'+$stamp)
New-Item -ItemType Directory -Force -Path $work|Out-Null
try{
  foreach($relative in @('config','data\business')){
    $source=Join-Path $root $relative
    if(Test-Path -LiteralPath $source){
      $destination=Join-Path $work $relative
      New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent)|Out-Null
      Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
    }
  }
  Push-Location $work
  tar.exe -a -c -f $backup .
  if($LASTEXITCODE -ne 0){throw 'Nie udalo sie utworzyc backupu danych.'}
  Pop-Location
  $parent=Split-Path -Parent $root
  $cleanup=Join-Path $env:TEMP ('REMOVE_JARVIS_'+$stamp+'.cmd')
  Set-Content -LiteralPath $cleanup -Encoding ASCII -Value @"
@echo off
timeout /t 2 /nobreak >nul
rmdir /s /q "$root"
del /f /q "%~f0"
"@
  Start-Process -FilePath $cleanup -WorkingDirectory $parent
}finally{
  if((Get-Location).Path -eq $work){Pop-Location}
  Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host ('Backup danych: '+$backup)
'''
