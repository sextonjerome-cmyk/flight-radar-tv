@echo off
rem ============================================================
rem  Flight Radar TV  -  set the display to YOUR home airport
rem  Downloads the map, approaches, airspace, weather, and
rem  radio frequencies for the airport you enter. One time.
rem ============================================================
cd /d "%~dp0"

rem find Python (either "python" or "py")
set PY=python
where python >nul 2>nul || set PY=py
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo   Python is not installed. Get it free from https://python.org
  echo   During install, tick "Add Python to PATH", then run this again.
  echo.
  pause
  exit /b
)

echo.
echo   ==================================================
echo      Flight Radar TV  -  set up your home airport
echo   ==================================================
echo.
echo   Enter your airport's 4-letter ICAO code.
echo   Examples:  KLAX (Los Angeles)   KDEN (Denver)
echo              KJFK (New York)       KSEA (Seattle)
echo.
set /p ICAO="   Airport code: "
if "%ICAO%"=="" (echo   Nothing entered - exiting. & pause & exit /b)

echo.
echo   Setting up %ICAO%. This downloads a lot and takes a few
echo   minutes (longest the first time). Please wait...
echo.
%PY% setup_region.py %ICAO%

echo.
echo   All done. Double-click START-RADAR to watch your radar.
echo.
pause
