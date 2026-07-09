@echo off
rem FlightRadar TV — starts the local server and opens the radar.
rem The app must be served over http://localhost (not opened as a file)
rem so live data and LiveATC audio are allowed by the browser.
cd /d "%~dp0"
if not exist "mapdata\nav_data.js" (
  echo.
  echo   No airport is set up yet.
  echo   Double-click SETUP-AIRPORT first, enter your airport code, then run this again.
  echo.
  pause
  exit /b
)
rem free port 8478 if an old server is still running, so this is a clean restart
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8478 " ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>nul

start "" "http://localhost:8478/index.html"
python server.py 2>nul || py server.py
