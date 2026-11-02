@echo off
rem Updates the public site pcmarket.khudoberdi.uz: push, server update, frontend build, restart, check.
rem Works only from the alpha branch (deploy/deploy.sh refuses any other).
rem Details - docs/deploy.md. Needs Git for Windows (bash, ssh) and the SSH key of the server.
cd /d "%~dp0"
set BASH=%ProgramFiles%\Git\usr\bin\bash.exe
if not exist "%BASH%" set BASH=%ProgramFiles%\Git\bin\bash.exe
if not exist "%BASH%" (
    echo Git for Windows not found
    pause
    exit /b 1
)
rem _local (price lists, DB copies, server passwords) must never reach git: refuse if any of it is in the index
set GIT=%ProgramFiles%\Git\cmd\git.exe
if not exist "%GIT%" (
    echo Git for Windows not found
    pause
    exit /b 1
)
"%GIT%" ls-files -- _local | findstr . >nul
if not errorlevel 1 (
    echo REFUSED: files of _local are in the git index ^(git ls-files _local^). Remove them: git rm -r --cached _local
    pause
    exit /b 1
)
"%BASH%" -lc "cd \"$(cygpath '%~dp0')\" && bash deploy/deploy.sh"
if errorlevel 1 (
    echo Deploy failed, see the messages above.
    pause
    exit /b 1
)
pause
