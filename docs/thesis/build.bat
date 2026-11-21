@echo off
rem Build the thesis: Markdown sources -> ALT_STORES_VKR.docx -> Word updates the contents -> PDF.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv
  .venv\Scripts\python.exe -m pip install python-docx pymupdf matplotlib pywin32
)
.venv\Scripts\python.exe charts.py || goto :fail
.venv\Scripts\python.exe build.py || goto :fail
.venv\Scripts\python.exe render.py %* || goto :fail
echo.
echo Done: %~dp0ALT_STORES_VKR.docx and ALT_STORES_VKR.pdf
pause
exit /b 0
:fail
echo.
echo BUILD FAILED - see the ERROR lines above.
pause
exit /b 1
