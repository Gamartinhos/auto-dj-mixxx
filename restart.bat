@echo off
echo Encerrando o servidor atual...
taskkill /IM python.exe /F 2>nul
echo.
echo Iniciando o Auto DJ...
.venv\Scripts\python.exe main.py
pause
