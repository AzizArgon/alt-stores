@echo off
rem Smoke test of the site (Phase 20): opens the main pages and prints "ALL OK" or what did not open.
rem   smoke.bat         - the public site (run it after every deploy.bat)
rem   smoke.bat local   - the local site http://localhost:5173 (start.bat first)
rem Read-only: no logins, nothing is changed. The first run installs Playwright (about a minute).
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PY=scripts\smoke_test\.venv\Scripts\python.exe
if not exist "%PY%" (
    echo First run: installing Playwright into scripts\smoke_test\.venv ...
    py -3 -m venv scripts\smoke_test\.venv || python -m venv scripts\smoke_test\.venv
    "%PY%" -m pip install -q -r scripts\smoke_test\requirements.txt || (
        echo Could not install Playwright - check the internet and run smoke.bat again.
        pause
        exit /b 1
    )
)
"%PY%" scripts\smoke_test\smoke_test.py %*
set RESULT=%ERRORLEVEL%
if "%RESULT%"=="0" (echo. & echo === ALL OK ===) else (echo. & echo === PROBLEMS: see FAIL lines above ===)
pause
exit /b %RESULT%
