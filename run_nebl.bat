@echo off
title NEBL Live Stats
echo ========================================
echo      NEBL Live Stats Launcher
echo ========================================
echo.
echo Starting CSV writer (auto-refreshes every 5 seconds)...
start "CSV Writer" cmd /c "cd /d C:\Users\suppo\Documents\NEBL && python write_csv.py"

echo Starting GUI...
python nebl_app_v2.py
