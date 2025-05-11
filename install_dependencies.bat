@echo off
echo Installing required dependencies for Supabase integration...

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install the packages
pip install supabase toml

echo.
echo Dependencies installed!
echo.
echo You can now run:
echo python load_swedish_stocks.py
echo.

pause