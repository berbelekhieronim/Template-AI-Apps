@echo off
echo ========================================
echo INSTALACJA POLSKIEGO TTS dla Visual Search
echo ========================================
echo.

cd /d "%~dp0..\PsychoPy"

echo Instaluje gTTS (polski glos Google)...
python.exe -m pip install gtts

echo.
echo ========================================
echo SPRAWDZANIE INSTALACJI...
echo ========================================
python.exe -c "from gtts import gTTS; print('✓ gTTS zainstalowane poprawnie!')"

echo.
echo ========================================
echo GOTOWE!
echo ========================================
echo Uruchom: run_experiment.bat
echo.
pause
