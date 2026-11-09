@echo off
cd /d "%~dp0"
node scripts\gerar.mjs %*
echo.
echo Os videos ficam na pasta "videos".
pause
