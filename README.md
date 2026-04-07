# Voice Agent – Serverabfrage & CRM-Diktierung

**Tobias Dietz | yoka@provolution.org | Bewerbung Everlast**

Ein lokaler Python-Prototyp für sprachgesteuerte IT-Serverabfragen und CRM-Ticketerstellung. Der Agent nimmt gesprochene Anfragen entgegen, erkennt die Intention via LLM Tool Calling und gibt das Ergebnis als gesprochene Antwort zurück.

```
Mikrofon / WAV-Datei
        │
        ▼
  ┌─────────────┐
  │  faster-    │  Speech-to-Text (lokal, CPU)
  │  whisper    │
  └──────┬──────┘
         │ Transkript
         ▼
  ┌─────────────┐        ┌──────────────────────────┐
  │    Groq     │──────▶ │  get_server_status()     │
  │ llama-3.3-  │  Tool  │  create_ticket()          │  Mock-API
  │ 70b-vers.   │◀────── │                          │
  └──────┬──────┘ Result └──────────────────────────┘
         │ Natürlichsprachliche Antwort
         ▼
  ┌─────────────┐
  │  Piper TTS  │  Text-to-Speech (lokal, CPU)
  │  (Thorsten) │
  └──────┬──────┘
         │
         ▼
   Lautsprecher
```

---

## Architektur-Entscheidungen

### STT: faster-whisper

`faster-whisper` ist eine CTranslate2-optimierte Reimplementierung von Whisper (~216× RTF auf CPU).
Silero VAD ist direkt integriert (`vad_filter=True`), was leere Transkriptionen durch Rauschen verhindert.
Modell `base` für den Prototyp, `large-v3-turbo` empfohlen für Produktion.

### LLM: Groq + llama-3.3-70b-versatile (Tool Calling)

Statt Regex/Keyword-Matching werden zwei Tool-Definitionen direkt an die Groq API übergeben.
Das Modell entscheidet strukturiert welches Tool aufzurufen ist — Argumente werden per JSON-Schema validiert.
Zweistufiger API-Aufruf: Runde 1 erzeugt den Tool-Call, Runde 2 formuliert die natürlichsprachliche Antwort.
Keyword-Intent-Fallback greift automatisch wenn das Modell einen fehlerhaften Tool-Call generiert.

### TTS: Piper + Thorsten-Voice (pyttsx3 Fallback)

`piper-tts` mit `de_DE-thorsten-high` — natürliche deutsche Stimme, schneller als Echtzeit auf CPU, offline.
`pyttsx3` (Microsoft Hedda Desktop German) als automatischer Fallback ohne Modell-Download.

### Fehlerbehandlung: Dreistufig

- **STT**: Konfidenz-Schwellwert (0.6) + Nutzer-Rückfrage bei niedrigem Score
- **Tool**: Mock-API gibt immer strukturiertes Dict zurück, nie eine Exception
- **LLM**: `tool_use_failed` → Keyword-Fallback; leere Antwort → `_fallback_response()`

---

## Schnellstart

### Option A: Automatische Installation (empfohlen)

```
Doppelklick auf install.bat
```

Die `install.bat` erledigt alles automatisch:
- Python-Version prüfen
- Alle Pakete installieren
- Groq API Key abfragen und dauerhaft speichern
- Piper TTS Modell herunterladen
- Schnelltest durchführen

### Option B: Manuelle Installation

```bash
# 1. Abhängigkeiten installieren
python -m pip install -r requirements.txt

# 2. Groq API Key setzen (kostenlos: https://console.groq.com/keys)
# Windows PowerShell – dauerhaft:
[System.Environment]::SetEnvironmentVariable('GROQ_API_KEY', 'gsk_...', 'User')

# 3. Neues Terminal öffnen und testen
python main.py --text "Wie ist der Status von web-01?"
```

---

## Verwendung

```bash
# Interaktives Menü
start.bat

# Demo-Modus (alle 5 Testfälle)
python main.py --demo

# Direkttext (ohne Mikrofon)
python main.py --text "Status von db-01?"

# Mikrofon-Modus
python main.py

# WAV-Datei
python main.py --file anfrage.wav

# Debug-Logging
python main.py --demo --verbose
```

---

## Verfügbare Mock-Server

| Server ID  | Status   | Region    | Besonderheit              |
|------------|----------|-----------|---------------------------|
| web-01     | online   | Frankfurt | –                         |
| web-02     | online   | Frankfurt | –                         |
| db-01      | degraded | Amsterdam | CPU 88%, RAM 92%          |
| db-02      | offline  | Amsterdam | Wartungsfenster           |
| cache-01   | online   | Frankfurt | –                         |

---

## Testergebnisse (Demo-Lauf v1.3)

| # | Anfrage                        | Tool               | Latenz | Status  |
|---|--------------------------------|--------------------|--------|---------|
| 1 | Status web-01                  | get_server_status  | 0.6s   | ✅ PASS |
| 2 | Ist db-02 online?              | get_server_status  | 0.7s   | ✅ PASS |
| 3 | VPN-Ticket, Priorität hoch     | create_ticket      | 0.5s   | ✅ PASS |
| 4 | Status server-xyz-999          | get_server_status  | 0.8s   | ✅ PASS |
| 5 | Notiz: Kunde Müller, Angebot   | create_ticket      | 0.6s   | ✅ PASS |

**5/5 Tests bestanden | Ø Latenz: 0.64s | 0 halluzinierte Tool-Calls**

---

## Projektstruktur

```
Testaufgabe/
├── main.py          # Orchestrierung (--text, --file, --demo, Mikrofon)
├── agent.py         # Groq Tool-Calling-Loop (Kernlogik)
├── tools.py         # Mock-API + Tool-Definitionen
├── stt.py           # faster-whisper Wrapper
├── tts.py           # Piper TTS + pyttsx3 Fallback
├── config.py        # Konfiguration (Modelle, Server-Registry)
├── requirements.txt # Python-Abhängigkeiten
├── install.bat      # Automatische Erstinstallation (Windows)
└── start.bat        # Täglicher Start mit Menü (Windows)
```

---

## Bekannte Einschränkungen

- Sequenzielle Pipeline (kein Streaming) → 3–6s End-to-End-Latenz
- Tickets werden lokal in tickets.json gespeichert (kein echtes CRM-Backend)
- Für Mobile-Einsatz (Auto/Außendienst): Backend als FastAPI + native App

## Lizenz

MIT
