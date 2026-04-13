@echo off
cd /d "%~dp0"
if exist "..\PsychoPy\python.exe" (
  "..\PsychoPy\python.exe" app3_wykrywacz_klamstw.py
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3 app3_wykrywacz_klamstw.py
  ) else (
    python app3_wykrywacz_klamstw.py
  )
)
pause
