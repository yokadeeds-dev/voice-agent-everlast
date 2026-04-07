@echo off
chcp 65001 >nul
title Voice Agent – GitHub Setup

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║         Voice Agent – GitHub Repository Setup           ║
echo ║         Tobias Dietz  ^|  Bewerbung Everlast             ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Schritt 1: Git prüfen ─────────────────────────────────────────────────────
echo [1/5] Pruefe Git-Installation...
git --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  FEHLER: Git nicht gefunden!
    echo  Bitte Git installieren unter: https://git-scm.com/download/win
    echo  Nach der Installation diese Datei erneut ausfuehren.
    echo.
    start https://git-scm.com/download/win
    pause
    exit /b 1
)
for /f "tokens=3" %%v in ('git --version') do set GITVER=%%v
echo     OK – Git %GITVER% gefunden
echo.

:: ── Schritt 2: Git Konfiguration ──────────────────────────────────────────────
echo [2/5] Git Benutzer konfigurieren...
git config --global user.name "Tobias Dietz" >nul 2>&1
git config --global user.email "yoka@provolution.org" >nul 2>&1
echo     OK – Git User: Tobias Dietz ^<yoka@provolution.org^>
echo.

:: ── Schritt 3: Lokales Repository initialisieren ─────────────────────────────
echo [3/5] Lokales Git-Repository einrichten...
cd /d "%~dp0"

if exist ".git" (
    echo     OK – Git-Repository bereits vorhanden
) else (
    git init
    echo     OK – Git-Repository initialisiert
)
echo.

:: ── Schritt 4: Dateien hinzufügen und committen ───────────────────────────────
echo [4/5] Dateien zum Repository hinzufuegen...
git add main.py agent.py tools.py stt.py tts.py config.py
git add requirements.txt README.md .gitignore install.bat start.bat github_setup.bat
echo     OK – Dateien hinzugefuegt
echo.

git commit -m "Initial release v1.9 - Voice Agent Prototyp

- STT: faster-whisper large-v3-turbo (beste Deutsch-Qualitaet)
- LLM: Groq llama-3.3-70b-versatile mit Tool Calling
- TTS: Piper Thorsten-Voice + pyttsx3 Fallback
- Tools: get_server_status() + create_ticket() mit persistentem Speicher
- Latenz-Profiling pro Pipeline-Stufe
- install.bat: vollautomatische Ersteinrichtung
- start.bat: Menue fuer taeglichen Betrieb
- 5/5 Demo-Tests bestanden (Ø 0.64s Latenz)" >nul 2>&1

echo     OK – Initialer Commit erstellt
echo.

:: ── Schritt 5: GitHub Remote einrichten ──────────────────────────────────────
echo [5/5] GitHub Repository verknuepfen...
echo.
echo  Bitte jetzt ein neues Repository auf GitHub erstellen:
echo.
echo  1. Gehe zu: https://github.com/new
echo  2. Repository Name: voice-agent-everlast
echo  3. Beschreibung:    Voice Agent Prototyp - Bewerbung Everlast
echo  4. Sichtbarkeit:    Public (damit Everlast es sehen kann)
echo  5. NICHTS ankreuzen (kein README, keine .gitignore, keine Lizenz)
echo  6. Klicke: "Create repository"
echo.
echo  Danach erscheint auf GitHub eine URL wie:
echo  https://github.com/DEIN-USERNAME/voice-agent-everlast.git
echo.
start https://github.com/new
echo.
set /p REPO_URL="  Bitte GitHub-URL hier einfuegen (https://github.com/...): "

if "%REPO_URL%"=="" (
    echo.
    echo  WARNUNG: Keine URL eingegeben.
    echo  Bitte spaeter manuell ausfuehren:
    echo    git remote add origin https://github.com/DEIN-USERNAME/voice-agent-everlast.git
    echo    git branch -M main
    echo    git push -u origin main
    echo.
    pause
    exit /b 0
)

git remote add origin "%REPO_URL%" >nul 2>&1
git branch -M main >nul 2>&1
echo.
echo  Pushe Code zu GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo  HINWEIS: Falls du nach Anmeldedaten gefragt wirst:
    echo  - GitHub Token erstellen unter: https://github.com/settings/tokens
    echo  - Token als Passwort eingeben
    echo.
) else (
    echo.
    echo ╔══════════════════════════════════════════════════════════╗
    echo ║              ERFOLGREICH AUF GITHUB!                    ║
    echo ╠══════════════════════════════════════════════════════════╣
    echo ║  Dein Repo: %REPO_URL%
    echo ║  Teile diesen Link mit Everlast fuer die Bewerbung!     ║
    echo ╚══════════════════════════════════════════════════════════╝
)
echo.
pause
