@echo off
rem Sandbox: everything unlocked, separate profile save\sandbox.json
cd /d "%~dp0"
python main.py --sandbox %*
if errorlevel 1 pause
