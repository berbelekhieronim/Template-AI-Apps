@echo off
cd /d "%~dp0"
if exist "..\PsychoPy\python.exe" (
	"..\PsychoPy\python.exe" app2_wtyczka_antyimpuls.py
) else (
	where py >nul 2>nul
	if %errorlevel%==0 (
		py -3 app2_wtyczka_antyimpuls.py
	) else (
		python app2_wtyczka_antyimpuls.py
	)
)
pause
