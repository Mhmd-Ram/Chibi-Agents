@echo off
REM Launches the chibi daemon with a visible console (handy for debugging).
REM For a fully hidden launch, double-click start-chibi.vbs instead.
cd /d "%~dp0"
pythonw -m daemon
