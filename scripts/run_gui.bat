@echo off
setlocal
cd /d "%~dp0\.."
set PYTHONPATH=src
python -m autocoder_agent.gui.app
