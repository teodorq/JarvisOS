@echo off
setlocal
title Instalacja JARVIS OS
cd /d "%~dp0"

set "PYTHON_LAUNCHER=py -3.13"
%PYTHON_LAUNCHER% --version >nul 2>nul
if errorlevel 1 set "PYTHON_LAUNCHER=python"

%PYTHON_LAUNCHER% --version >nul 2>nul
if errorlevel 1 (
    echo Nie znaleziono Pythona 3.13.
    echo Zainstaluj Python 3.13 i uruchom instalator ponownie.
    goto :error
)

if not exist ".venv\Scripts\python.exe" (
    echo Tworzenie lokalnego srodowiska .venv...
    %PYTHON_LAUNCHER% -m venv .venv
    if errorlevel 1 goto :error
)

set "REQUIREMENTS=requirements-lock.txt"
if not exist "%REQUIREMENTS%" set "REQUIREMENTS=requirements.txt"

echo Instalowanie zweryfikowanych bibliotek JARVIS OS...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r "%REQUIREMENTS%"
if errorlevel 1 goto :error

echo.
echo Instalacja zakonczona.
pause
exit /b 0

:error
echo.
echo Instalacja nie powiodla sie.
pause
exit /b 1
