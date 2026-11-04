@echo off
title Parar Video Creator
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 5600 -State Listen -ErrorAction SilentlyContinue; if (-not $c) { 'O Video Creator nao esta aberto.'; exit }; $p = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess); Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'gerar_video|gerar_entrevista|tts_|compor_' } | % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Stop-Process -Id $c.OwningProcess,$p.ParentProcessId -Force -ErrorAction SilentlyContinue; 'Video Creator encerrado.'"
pause
