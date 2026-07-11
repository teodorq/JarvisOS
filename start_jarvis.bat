@echo off
cd /d C:\JarvisAI
call .venv\Scripts\activate.bat
start "" pythonw.exe main.py
exit