@echo off
echo ========================================
echo NEBL Live Stats Runner
echo ========================================
echo.
echo This will:
echo 1. Start a background process to fetch live data every 15 seconds
echo 2. Open the live stats webpage
echo.
echo To stop: close this window or press Ctrl+C
echo.

REM Start the Python watch script in background
start /B python pbp_watch.py --url "https://nebl.web.geniussports.com/competitions/?WHurl=%2Fcompetition%2F48108%2Fmatch%2F2799695%2Fplaybyplay%3F" --game-id 2799695 --poll 15 --out data/debug_live.json > watch.log 2>&1

echo Watch process started...
echo.

REM Start HTTP server and open browser
echo Starting web server...
start /B python -m http.server 8000

echo Server started at http://localhost:8000
echo.
echo Opening liveresults.html in browser...
start http://localhost:8000/liveresults.html

echo.
echo ========================================
echo READY! 
echo - Web UI: http://localhost:8000/liveresults.html
echo - JSON data: http://localhost:8000/data/debug_live.json
echo.
echo Press any key to exit (will stop data fetching)...
pause > nul
