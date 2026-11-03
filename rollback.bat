@echo off
rem Returns the public site to the previous version (images kept by deploy.bat); the database is not touched.
rem Running it again returns the newer version. Details - docs/deploy.md.
cd /d "%~dp0"
set BASH=%ProgramFiles%\Git\usr\bin\bash.exe
if not exist "%BASH%" set BASH=%ProgramFiles%\Git\bin\bash.exe
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && bash deploy/rollback.sh"
pause
