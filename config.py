"""
config.py – Zentrale Konfiguration des Voice Agents
"""

import os

# ── Groq API ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"    # kostenlos, Tool Calling unterstützt

# ── STT (faster-whisper) ───────────────────────────────────────────────────────
WHISPER_MODEL = "large-v3-turbo"  # beste Deutsch-Qualität auf CPU, ~216x RTF
WHISPER_LANGUAGE = "de"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"   # int8 spart RAM auf CPU

# ── TTS (piper-tts) ────────────────────────────────────────────────────────────
PIPER_MODEL = "de_DE-thorsten-high"   # Fallback: pyttsx3, wenn Piper nicht verfügbar
PIPER_SAMPLE_RATE = 22050

# ── Audio-Aufnahme ─────────────────────────────────────────────────────────────
MIC_SAMPLE_RATE = 16000         # Whisper bevorzugt 16 kHz
MIC_CHANNELS = 1
MIC_RECORD_SECONDS = 6          # Max. Aufnahmedauer pro Utterance
MIC_SILENCE_THRESHOLD = 0.01    # RMS-Schwellwert für Stille-Erkennung
MIC_SILENCE_DURATION = 0.8      # Sekunden Stille → Aufnahme beenden (0.8s statt 1.5s = ~700ms gespart)

# ── Sicherheit / User-Context ──────────────────────────────────────────────────
DEFAULT_USER = "Unbekannt"      # Wird überschrieben durch --user Parameter
AUDIT_LOG_FILE = "audit.log"    # Audit-Log: Wer hat wann was abgefragt

# ── Mock-Server-Registry ───────────────────────────────────────────────────────
KNOWN_SERVERS = {
    "web-01": {
        "status": "online",
        "cpu": 34,
        "ram": 61,
        "uptime_h": 720,
        "region": "Frankfurt",
    },
    "web-02": {
        "status": "online",
        "cpu": 12,
        "ram": 45,
        "uptime_h": 1440,
        "region": "Frankfurt",
    },
    "db-01": {
        "status": "degraded",
        "cpu": 88,
        "ram": 92,
        "uptime_h": 48,
        "region": "Amsterdam",
        "alert": "Hohe Last – bitte prüfen",
    },
    "db-02": {
        "status": "offline",
        "cpu": 0,
        "ram": 0,
        "uptime_h": 0,
        "region": "Amsterdam",
        "alert": "Wartungsfenster aktiv bis 02:00 Uhr",
    },
    "cache-01": {
        "status": "online",
        "cpu": 5,
        "ram": 30,
        "uptime_h": 2160,
        "region": "Frankfurt",
    },
}

# ── Ticket-System ──────────────────────────────────────────────────────────────
TICKET_COUNTER_START = 5001
