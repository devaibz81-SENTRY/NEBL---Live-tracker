@echo off
title NEBL Live Stats
echo ========================================
echo      NEBL Live Stats Launcher
echo ========================================
echo.
set /p GAME_URL="Enter game URL: "
echo.

echo Starting CSV/TXT/XML writer (updates every 5 seconds)...
start "NEBL Writer" cmd /c "cd /d C:\Users\suppo\Documents\NEBL && python write_csv.py %GAME_URL%"

echo Starting GUI...
python nebl_app_v2.py
