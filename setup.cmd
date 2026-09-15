@echo off
rem One-command setup for Windows. Double-click it, or run from a terminal with options:
rem   setup.cmd            set everything up
rem   setup.cmd --run      ...then start the server and launch the app
rem   setup.cmd --help     all options
setlocal
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=pwsh"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set EXITCODE=%ERRORLEVEL%
rem keep the window open when double-clicked so the output can be read
if "%~1"=="" pause
exit /b %EXITCODE%
