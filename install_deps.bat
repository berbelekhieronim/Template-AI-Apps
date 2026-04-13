@echo off
cd /d "%~dp0"
echo Installing student dependencies...
if exist "PsychoPy\python.exe" (
  "PsychoPy\python.exe" -m pip install -r requirements-students.txt
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3 -m pip install -r requirements-students.txt
  ) else (
    python -m pip install -r requirements-students.txt
  )
)
echo Done.
pause
