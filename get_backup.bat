@echo off
rem Downloads the newest database backup of the public site to _local\backups\server\ (docs/deploy.md).
rem _local = the folder outside git: <repo>\_local, or ALT_LOCAL_DIR; the Task Scheduler runs a copy from _local\tools\
cd /d "%~dp0"
if not defined ALT_LOCAL_DIR if exist "%~dp0_local\" (set "ALT_LOCAL_DIR=%~dp0_local") else (set "ALT_LOCAL_DIR=%~dp0..")
for %%I in ("%ALT_LOCAL_DIR%") do set "ALT_LOCAL_DIR=%%~fI"
set BASH=%ProgramFiles%\Git\usr\bin\bash.exe
if not exist "%BASH%" set BASH=%ProgramFiles%\Git\bin\bash.exe
rem "auto" = started by the Task Scheduler: nobody is there to press a key, the result goes to a log
if /i "%~1"=="auto" goto auto
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && bash deploy/get_backup.sh"
pause
exit /b %ERRORLEVEL%

:auto
if not exist "%ALT_LOCAL_DIR%\backups\server\" mkdir "%ALT_LOCAL_DIR%\backups\server"
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && date '+%%F %%T' && bash deploy/get_backup.sh" >> "%ALT_LOCAL_DIR%\backups\server\get_backup.log" 2>&1
exit /b %ERRORLEVEL%
