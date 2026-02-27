@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel%==0 (
    python borehole_stick_gui.py
) else (
    py borehole_stick_gui.py
)

endlocal
