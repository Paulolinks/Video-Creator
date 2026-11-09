@echo off
cd /d "%~dp0"
echo Instalando (so na primeira vez, pode levar alguns minutos)...
where node >nul 2>nul || (echo Node.js nao encontrado. Instale em https://nodejs.org (versao LTS) e rode de novo. & pause & exit /b 1)
call npm install
echo.
echo Pronto. Agora coloque um roteiro na pasta "roteiros" e de dois cliques em gerar-video.bat
pause
