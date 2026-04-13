@echo off
cd /d "%~dp0"
if exist "..\PsychoPy\python.exe" (
	"..\PsychoPy\python.exe" app1_zdrowy_wybor.py
) else (
	where py >nul 2>nul
	if %errorlevel%==0 (
		py -3 app1_zdrowy_wybor.py
	) else (
		python app1_zdrowy_wybor.py
	)
)
pause
