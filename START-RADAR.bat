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
start "" "http://localhost:8478/index.html"
python server.py 2>nul || py server.py
