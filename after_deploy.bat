@echo off
rem After deploy.bat or before a demo: re-check flags, refresh demo builds, data counts, memory, disk (one ssh connection).
rem Does not change Age Computers, prices or passwords. Details - docs/maintenance.md.
cd /d "%~dp0"
set BASH=%ProgramFiles%\Git\usr\bin\bash.exe
if not exist "%BASH%" set BASH=%ProgramFiles%\Git\bin\bash.exe
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && bash deploy/after_deploy.sh"
pause
