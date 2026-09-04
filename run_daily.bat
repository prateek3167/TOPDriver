@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python etl_pipeline.py >> logs\daily_task.log 2>&1
deactivate