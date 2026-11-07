@echo off
rem Cierra el overlay de AoE2 Coaching (y el demo, si esta abierto).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*overlay.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
