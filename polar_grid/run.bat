@echo off
echo ================================================
echo   PolarGrid AI - Starting Server...
echo ================================================
echo.
echo Installing dependencies (first time only)...
pip install fastapi uvicorn scikit-learn numpy pandas scipy --quiet
echo.
echo Starting PolarGrid AI Dashboard...
echo Open http://localhost:8000 in your browser
echo.
python backend/main.py
pause
