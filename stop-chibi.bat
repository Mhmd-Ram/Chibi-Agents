@echo off
REM Stops any running chibi daemon by hitting the HTTP /quit endpoint or killing pythonw.
REM Simpler approach: kill pythonw processes running the daemon module.
taskkill /F /FI "WINDOWTITLE eq Chibi Pets" >nul 2>&1
for /f "tokens=2" %%i in ('wmic process where "name='pythonw.exe' and commandline like '%%daemon%%'" get processid /value 2^>nul ^| find "="') do taskkill /F /PID %%i >nul 2>&1
echo Done.
