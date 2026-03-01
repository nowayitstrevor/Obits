@echo off
echo Starting Waco Obituary Aggregator Web UI...
echo.
echo Make sure you have Python and the virtual environment set up.
echo.

cd /d "c:\Users\Noway\OneDrive\Documents\Obit Scraper"

if not exist ".venv\Scripts\python.exe" (
    echo Error: Virtual environment not found!
    echo Please make sure the .venv directory exists and contains Python.
    pause
    exit /b 1
)

echo Activating virtual environment...
call .venv\Scripts\activate

echo Starting Flask web server...
echo Open your browser to: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

python web_ui.py

pause
