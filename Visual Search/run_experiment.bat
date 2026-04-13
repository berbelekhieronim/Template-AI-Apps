@echo off
REM Visual Search Experiment Launcher
cd /d "%~dp0"
echo Starting Visual Search experiment...
if exist "..\PsychoPy\python.exe" (
	"..\PsychoPy\python.exe" visual_search_experiment.py
) else (
	where py >nul 2>nul
	if %errorlevel%==0 (
		py -3 visual_search_experiment.py
	) else (
		python visual_search_experiment.py
	)
)
pause
