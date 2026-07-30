@echo off
setlocal
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
start "CareerTwin Flask API" cmd /k "call .venv\Scripts\activate && python backend\app.py"
timeout /t 3 /nobreak >nul
streamlit run frontend\streamlit_app.py
