@echo off
chcp 65001 >nul
pushd %~dp0
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
popd
