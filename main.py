"""
main.py – Voice Agent Hauptschleife

Startmodi:
  python main.py                  → Interaktive Schleife mit Mikrofon
  python main.py --file audio.wav → Einzelne WAV-Datei verarbeiten
  python main.py --text "..."     → Textdirektmodus (ohne STT, für Tests)
  python main.py --demo           → Demo mit vordefinierten Anfragen

Architektur: STT → Agent (LLM + Tool Calling) → TTS
"""

import argparse
import io
import logging
import sys
import time

# Windows: UTF-8-Ausgabe erzwingen (verhindert Umlaut-Darstellungsfehler in PowerShell)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import (
    GROQ_API_KEY,
    MIC_CHANNELS,
    MIC_RECORD_SECONDS,
    MIC_SAMPLE_RATE,
    MIC_SILENCE_DURATION,
    MIC_SILENCE_THRESHOLD,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
)
from stt import SpeechToText
from tts import TextToSpeech
from agent import VoiceAgent

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# Demo-Anfragen für --demo-Modus
DEMO_QUERIES = [
    "Wie ist der Status von web-01?",
    "Ist db-02 online?",
    "Bitte erstell ein Ticket: Der VPN-Client lässt sich nicht starten, Priorität hoch.",
    "Was ist der Status von server-xyz-999?",
    "Notiz diktieren: Kunde Müller braucht ein Angebot bis Freitag.",
]

# Befehle zum Beenden der interaktiven Schleife
EXIT_COMMANDS = {"exit", "quit", "beenden", "ende", "stopp", "stop"}


def print_banner():
    print("\n" + "═" * 60)
    print("  🎙️  Voice Agent – Serverabfrage & CRM-Diktierung")
    print("═" * 60)
    print("  Befehle: 'exit' oder 'quit' zum Beenden")
    print("  Sprache: Deutsch")
    print("═" * 60 + "\n")


def run_pipeline(user_text: str, agent: VoiceAgent, tts: TextToSpeech) -> str:
    """
    Führt Agent + TTS für einen gegebenen Text aus.
    Gibt die generierte Antwort zurück.
    """
    print(f"\n🎤 Nutzer: {user_text}")

    # ── Latenz-Messung je Pipeline-Stufe ──────────────────────────────────────
    t_total = time.time()

    t_llm = time.time()
    answer = agent.process(user_text)
    llm_ms = int((time.time() - t_llm) * 1000)

    t_tts = time.time()
    print(f"🤖 Agent ({llm_ms}ms LLM): {answer}")
    print(f"🔊 Spreche Antwort aus …")
    tts.speak(answer)
    tts_ms = int((time.time() - t_tts) * 1000)

    total_ms = int((time.time() - t_total) * 1000)

    logger.info(
        f"Latenz-Profil → LLM: {llm_ms}ms | TTS: {tts_ms}ms | "
        f"Gesamt: {total_ms}ms"
    )
    print(f"⏱️  LLM: {llm_ms}ms | TTS: {tts_ms}ms | Gesamt: {total_ms}ms\n")
    return answer


def mode_microphone(agent: VoiceAgent, stt: SpeechToText, tts: TextToSpeech):
    """Interaktive Mikrofon-Schleife."""
    print_banner()
    print("Drücke Enter zum Starten der Aufnahme (oder 'exit' zum Beenden).\n")

    while True:
        cmd = input("→ Enter drücken oder 'exit': ").strip().lower()
        if cmd in EXIT_COMMANDS or cmd == "exit":
            print("Voice Agent beendet.")
            break

        print("🎙️  Aufnahme läuft …")
        result = stt.record_from_microphone(
            sample_rate=MIC_SAMPLE_RATE,
            max_seconds=MIC_RECORD_SECONDS,
            silence_threshold=MIC_SILENCE_THRESHOLD,
            silence_duration=MIC_SILENCE_DURATION,
        )

        if result.error:
            msg = f"Aufnahmefehler: {result.error}"
            logger.error(msg)
            tts.speak("Bei der Aufnahme ist ein Fehler aufgetreten. Bitte erneut versuchen.")
            continue

        if result.is_empty:
            print("⚠️  Keine Sprache erkannt. Bitte erneut versuchen.")
            tts.speak("Ich habe nichts gehört. Bitte erneut sprechen.")
            continue

        if result.low_confidence:
            print(f"⚠️  Niedrige Erkennungssicherheit ({result.confidence:.0%}): '{result.text}'")
            tts.speak(
                f"Ich habe folgendes verstanden: {result.text}. "
                "Ist das korrekt? Bitte bestätigen oder wiederholen."
            )
            confirm = input("Bestätigen? (j/n): ").strip().lower()
            if confirm != "j":
                print("Abgebrochen. Bitte erneut sprechen.")
                continue

        run_pipeline(result.text, agent, tts)


def mode_file(path: str, agent: VoiceAgent, stt: SpeechToText, tts: TextToSpeech):
    """Verarbeitet eine einzelne WAV-Datei."""
    print_banner()
    print(f"📂 Verarbeite Datei: {path}\n")

    result = stt.transcribe_file(path)

    if result.error:
        logger.error(f"STT-Fehler: {result.error}")
        print(f"❌ Fehler: {result.error}")
        sys.exit(1)

    if result.is_empty:
        print("⚠️  Keine Sprache in der Datei erkannt.")
        sys.exit(0)

    if result.low_confidence:
        print(f"⚠️  Niedrige Erkennungssicherheit ({result.confidence:.0%})")

    run_pipeline(result.text, agent, tts)


def mode_text(text: str, agent: VoiceAgent, tts: TextToSpeech):
    """Direktmodus: Text ohne STT verarbeiten."""
    print_banner()
    run_pipeline(text, agent, tts)


def mode_demo(agent: VoiceAgent, tts: TextToSpeech):
    """Demo-Modus mit vordefinierten Anfragen."""
    print_banner()
    print("🚀 Demo-Modus: Führe vordefinierte Anfragen aus …\n")

    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"── Demo {i}/{len(DEMO_QUERIES)} ──────────────────────────")
        run_pipeline(query, agent, tts)
        if i < len(DEMO_QUERIES):
            time.sleep(1.5)

    print("Demo abgeschlossen.")


def main():
    parser = argparse.ArgumentParser(
        description="Voice Agent – Serverabfragen und CRM-Diktierung per Sprache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python main.py                          # Mikrofon-Modus
  python main.py --file anfrage.wav       # WAV-Datei
  python main.py --text "Status web-01"  # Direkttext
  python main.py --demo                   # Demo-Modus
        """,
    )
    parser.add_argument("--file", metavar="WAV", help="WAV-Datei als Input")
    parser.add_argument("--text", metavar="TEXT", help="Direkt-Text-Input (ohne STT)")
    parser.add_argument("--demo", action="store_true", help="Demo-Modus")
    parser.add_argument("--tts-engine", choices=["piper", "pyttsx3"], default="piper",
                        help="TTS-Engine (Standard: piper)")
    parser.add_argument("--whisper-model", default=WHISPER_MODEL,
                        help=f"Whisper-Modell (Standard: {WHISPER_MODEL})")
    parser.add_argument("--verbose", action="store_true", help="Debug-Logging aktivieren")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Initialisierung ────────────────────────────────────────────────────────
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY nicht gesetzt.")
        print("   $env:GROQ_API_KEY='gsk_...'")
        sys.exit(1)

    print("⚙️  Initialisiere Komponenten …")

    tts = TextToSpeech(preferred_engine=args.tts_engine)

    # STT wird nur im Mikrofon- oder Datei-Modus benötigt
    stt = None
    if not args.text and not args.demo:
        stt = SpeechToText(
            model_size=args.whisper_model,
            language=WHISPER_LANGUAGE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

    try:
        agent = VoiceAgent()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print("✅ Bereit.\n")

    # ── Modus-Dispatch ─────────────────────────────────────────────────────────
    if args.demo:
        mode_demo(agent, tts)
    elif args.text:
        mode_text(args.text, agent, tts)
    elif args.file:
        mode_file(args.file, agent, stt, tts)
    else:
        mode_microphone(agent, stt, tts)


if __name__ == "__main__":
    main()
