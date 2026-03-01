@echo off
echo Starting Enhanced Waco Obituary Aggregator...
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install/update required packages
echo Installing required packages...
pip install flask flask-cors requests beautifulsoup4 selenium webdriver-manager

echo.
echo Starting web application...
echo You can access the interface at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the application
echo.

REM Start the enhanced web UI
python enhanced_web_ui.py

pause
