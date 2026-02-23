@echo off
echo ========================================
echo NEBL Live Stats - Local Fetcher
echo ========================================
echo.

REM Install requirements
echo Installing requirements...
pip install requests beautifulsoup4 playwright google-api-python-client
playwright install chromium
echo.

REM Set credentials - Replace with your actual JSON
echo Note: Set GOOGLE_CREDENTIALS_JSON environment variable
echo Example: set GOOGLE_CREDENTIALS_JSON={"your json here"}
echo.

REM Run the fetcher
echo Running local_fetcher.py...
python local_fetcher.py

pause
