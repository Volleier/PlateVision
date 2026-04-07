@echo off
REM Start backend (Flask) and frontend (Streamlit) in separate windows

REM Edit these if your environment or project path differ
set "CONDA_ENV=PlateVision"
set "PROJECT_DIR=E:\Project\PlateVision"

echo Starting PlateVision services using Conda environment: %CONDA_ENV%

REM Start backend in a new cmd window
start "Backend - PlateVision" cmd /k "call conda activate %CONDA_ENV% && cd /d %PROJECT_DIR%\backend && python App.py"

REM Small delay to avoid mixed output on startup
timeout /t 2 >nul

REM Start frontend (Streamlit) in a new cmd window
start "Frontend - PlateVision" cmd /k "call conda activate %CONDA_ENV% && cd /d %PROJECT_DIR%\frontend && streamlit run app.py"

exit /b 0
