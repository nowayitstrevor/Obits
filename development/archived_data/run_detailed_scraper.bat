@echo off
cd /d "c:\Users\Noway\OneDrive\Documents\Obit Scraper"
echo.
echo ===================================================
echo          REAL LAKE SHORE OBITUARY SCRAPER
echo ===================================================
echo.
echo This will scrape REAL obituaries from:
echo https://www.lakeshorefuneralhome.com/obituaries/obituary-listings
echo.
echo Expected to find real obituaries like:
echo - Bobbie Jean Gaskamp (Mar 06, 1947 - Jul 22, 2025)
echo - Danny Ellis (Dec 07, 1957 - Jul 21, 2025) 
echo - Rocky Byrd (Oct 31, 1953 - Jul 17, 2025)
echo - And more current obituaries...
echo.
echo Starting Firefox-based scraper...
"C:\Users\Noway\OneDrive\Documents\Obit Scraper\.venv\Scripts\python.exe" scrape_real_obituaries.py
echo.
echo ===================================================
echo Scraper completed! 
echo Check obituaries_detailed.json for results.
echo Refresh your web UI to see the real obituaries!
echo ===================================================
pause
