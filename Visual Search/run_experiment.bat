@echo off
REM Visual Search Experiment Launcher
cd /d "%~dp0"
echo Starting Visual Search experiment...
..\PsychoPy\python.exe visual_search_experiment.py
pause
