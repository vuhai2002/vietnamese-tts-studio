@echo off
rem Mo giao dien web Omnivoice Tieng Viet (double-click la chay).
rem Browser se tu mo tai http://127.0.0.1:7860
cd /d "%~dp0"
set PYTHONUTF8=1
uv run python web_server.py
pause
