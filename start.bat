@echo off
chcp 65001 >nul
title Voice Agent – Tobias Dietz

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║         Voice Agent – Serverabfrage ^& CRM               ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo  Optionen:
echo  [1] Demo-Modus         (alle 5 Testfaelle)
echo  [2] Text eingeben      (ohne Mikrofon)
echo  [3] Mikrofon           (Live-Aufnahme)
echo  [4] WAV-Datei          (Datei angeben)
echo  [5] Beenden
echo.
set /p CHOICE="Auswahl (1-5): "

if "%CHOICE%"=="1" (
    python main.py --demo
) else if "%CHOICE%"=="2" (
    set /p USERTEXT="Anfrage eingeben: "
    python main.py --text "%USERTEXT%"
) else if "%CHOICE%"=="3" (
    python main.py
) else if "%CHOICE%"=="4" (
    set /p WAVFILE="Pfad zur WAV-Datei: "
    python main.py --file "%WAVFILE%"
) else if "%CHOICE%"=="5" (
    exit /b 0
) else (
    echo Ungueltige Auswahl.
)
echo.
pause
