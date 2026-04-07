@echo off
chcp 65001 >nul
title Voice Agent – Installation & Setup

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║       Voice Agent – Automatische Installation           ║
echo ║       Tobias Dietz  ^|  Bewerbung Everlast               ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Schritt 1: Python prüfen ──────────────────────────────────────────────────
echo [1/6] Pruefe Python-Installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo FEHLER: Python nicht gefunden!
    echo Bitte Python 3.11 installieren: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo     OK – Python %PYVER% gefunden
echo.

:: ── Schritt 2: Requirements installieren ─────────────────────────────────────
echo [2/6] Installiere Python-Abhaengigkeiten...
echo     (Das kann 2-5 Minuten dauern beim ersten Mal)
echo.
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo FEHLER: Installation fehlgeschlagen!
    echo Bitte Internetverbindung pruefen und erneut versuchen.
    pause
    exit /b 1
)
echo.
echo     OK – Alle Pakete installiert
echo.

:: ── Schritt 3: Groq API Key ───────────────────────────────────────────────────
echo [3/6] Groq API Key einrichten...
echo.
set EXISTING_KEY=
for /f "tokens=*" %%k in ('powershell -Command "[System.Environment]::GetEnvironmentVariable(\"GROQ_API_KEY\", \"User\")"') do set EXISTING_KEY=%%k

if not "%EXISTING_KEY%"=="" (
    echo     OK – GROQ_API_KEY bereits gesetzt
    echo     Key: %EXISTING_KEY:~0,12%...
) else (
    echo     GROQ_API_KEY ist noch nicht gesetzt.
    echo     Kostenloser Key unter: https://console.groq.com/keys
    echo.
    set /p USER_KEY="     Key eingeben (gsk_...): "
    if not "%USER_KEY%"=="" (
        powershell -Command "[System.Environment]::SetEnvironmentVariable('GROQ_API_KEY', '%USER_KEY%', 'User')"
        set GROQ_API_KEY=%USER_KEY%
        echo     OK – Key dauerhaft gespeichert
    ) else (
        echo     WARNUNG: Kein Key eingegeben. Bitte spaeter manuell setzen.
    )
)
echo.

:: ── Schritt 4: Piper TTS Modell ───────────────────────────────────────────────
echo [4/6] Pruefe Piper TTS Modell (Thorsten-Voice)...
set PIPER_DIR=%USERPROFILE%\.local\share\piper
set PIPER_MODEL=%PIPER_DIR%\de_DE-thorsten-high.onnx

if exist "%PIPER_MODEL%" (
    echo     OK – Piper-Modell bereits vorhanden
) else (
    echo     Piper-Modell nicht gefunden – wird heruntergeladen (108 MB^)...
    if not exist "%PIPER_DIR%" mkdir "%PIPER_DIR%"
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx' -OutFile '%PIPER_MODEL%' -Headers @{'User-Agent'='Mozilla/5.0'}"
    powershell -Command "Invoke-WebRequest -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json' -OutFile '%PIPER_MODEL%.json' -Headers @{'User-Agent'='Mozilla/5.0'}"
    if exist "%PIPER_MODEL%" (
        echo     OK – Piper-Modell heruntergeladen
    ) else (
        echo     WARNUNG: Download fehlgeschlagen – Fallback auf pyttsx3 wird genutzt
    )
)
echo.

:: ── Schritt 5: Schnelltest ────────────────────────────────────────────────────
echo [5/6] Fuehre Schnelltest der Mock-API durch...
python -c "from tools import get_server_status, create_ticket; r=get_server_status('web-01'); print('    OK –', r['server_id'], 'ist', r['status'])" 2>nul
if errorlevel 1 (
    echo     WARNUNG: Mock-API Test fehlgeschlagen
) else (
    echo     OK – Mock-API funktioniert
)
echo.

:: ── Schritt 6: Abschluss ──────────────────────────────────────────────────────
echo [6/6] Installation abgeschlossen!
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                  FERTIG! Verwendung:                    ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║  Demo starten:    python main.py --demo                  ║
echo ║  Text-Test:       python main.py --text "Status web-01" ║
echo ║  Mikrofon:        python main.py                         ║
echo ║  WAV-Datei:       python main.py --file audio.wav        ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
set /p RUNDEMO="Demo-Modus jetzt starten? (j/n): "
if /i "%RUNDEMO%"=="j" (
    echo.
    python main.py --demo
)
echo.
pause
