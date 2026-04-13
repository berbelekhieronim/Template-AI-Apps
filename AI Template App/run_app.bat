@echo off
cd /d "%~dp0"
if exist "..\PsychoPy\python.exe" (
	"..\PsychoPy\python.exe" ai_template_app.py
) else (
	where py >nul 2>nul
	if %errorlevel%==0 (
		py -3 ai_template_app.py
	) else (
		python ai_template_app.py
	)
)
pause
