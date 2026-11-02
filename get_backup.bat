@echo off
rem Downloads the newest database backup of the public site to F:\claudy\backups\server\ (docs/deploy.md).
cd /d "%~dp0"
set BASH=%ProgramFiles%\Git\usr\bin\bash.exe
if not exist "%BASH%" set BASH=%ProgramFiles%\Git\bin\bash.exe
rem "auto" = started by the Task Scheduler: nobody is there to press a key, the result goes to a log
if /i "%~1"=="auto" goto auto
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && bash deploy/get_backup.sh"
pause
exit /b %ERRORLEVEL%

:auto
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && date '+%%F %%T' && bash deploy/get_backup.sh" >> "F:\claudy\backups\server\get_backup.log" 2>&1
exit /b %ERRORLEVEL%
