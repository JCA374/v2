@echo off
echo Installing dependencies for Stock Analysis app...
echo.

REM Check if virtual environment exists
if not exist .venv\Scripts\activate.bat (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install requirements
echo Installing required packages...
pip install -r requirements.txt

echo.
echo Setup complete! You can now run the application with:
echo streamlit run app.py
echo.
echo Or load Swedish stocks data with:
echo python load_swedish_stocks.py
echo.

pause