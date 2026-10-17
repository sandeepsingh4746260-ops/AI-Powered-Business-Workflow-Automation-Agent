@echo off
cd /d "%~dp0"
py -m streamlit run app/main.py
pause
