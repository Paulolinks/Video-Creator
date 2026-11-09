@echo off
cd /d "%~dp0"
echo Abrindo o estudio de pre-visualizacao no navegador...
call npx remotion studio src/index.ts
