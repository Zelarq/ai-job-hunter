@echo off
cd /d "%~dp0"
echo Starting Bangalore Career-Page Job Scraper...
call "venv\Scripts\python.exe" main.py
echo.
echo Job run finished. Check data/ and logs/run.log for details.
