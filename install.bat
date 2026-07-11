@echo off
title Instalacja JARVIS OS

echo ===========================
echo Instalacja bibliotek JARVIS
echo ===========================

python -m pip install --upgrade pip

pip install -r requirements.txt

echo.
echo Instalacja zakonczona.
pause