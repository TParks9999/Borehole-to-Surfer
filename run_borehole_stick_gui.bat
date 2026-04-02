@echo off
setlocal
cd /d "%~dp0"

set "BOOTSTRAP_PY="
where python >nul 2>&1
if %errorlevel%==0 (
    set "BOOTSTRAP_PY=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "BOOTSTRAP_PY=py -3"
    )
)

if not defined BOOTSTRAP_PY (
    echo Could not find Python.
    echo Install Python 3.10+ and try again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv...
    %BOOTSTRAP_PY% -m venv .venv
    if not %errorlevel%==0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "PYTHON_EXE=.venv\Scripts\python.exe"

%PYTHON_EXE% -c "import numpy, pandas, shapefile, PIL, pyproj" >nul 2>&1
if not %errorlevel%==0 (
    echo Installing required packages from requirements.txt...
    %PYTHON_EXE% -m pip install -r requirements.txt
    if not %errorlevel%==0 (
        echo.
        echo Failed to install requirements.
        echo Run this manually and retry:
        echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

%PYTHON_EXE% borehole_stick_gui.py
if not %errorlevel%==0 (
    echo.
    echo App failed to start.
    pause
    exit /b 1
)

endlocal
