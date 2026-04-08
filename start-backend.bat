@echo off
cd /d C:\laragon\www\ai-team\backend
C:\laragon\bin\python\python-3.13\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause

