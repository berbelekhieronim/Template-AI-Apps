@echo off
cd /d "%~dp0"
if exist "..\PsychoPy\python.exe" (
  "..\PsychoPy\python.exe" app4_malowanie_glosem_i_wzrokiem.py
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3 app4_malowanie_glosem_i_wzrokiem.py
  ) else (
    python app4_malowanie_glosem_i_wzrokiem.py
  )
)
pause
