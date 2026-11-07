@echo off
rem Cierra AoE2 Coaching (desde el codigo o el .exe), y el demo si esta abierto.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'AoE2Coaching.exe' -or $_.CommandLine -like '*aoe2c.py*' -or $_.CommandLine -like '*overlay.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
