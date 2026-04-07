"""
tts.py – Text-to-Speech Wrapper

Primär:  piper-tts mit Thorsten-Voice (de_DE-thorsten-high)
Fallback: pyttsx3 (System-TTS, kein Modell-Download nötig)

Piper wird beim ersten Aufruf automatisch erkannt.
Ist es nicht installiert, wird auf pyttsx3 zurückgefallen.
Audio-Output: Standardlautsprecher (sounddevice/scipy) oder WAV-Datei.
"""

import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    TTS-Wrapper mit automatischem Engine-Fallback.

    Reihenfolge:
      1. piper-tts  (Thorsten-Voice, hohe Qualität, lokal)
      2. pyttsx3    (System-Engine, synthetisch aber zuverlässig)
    """

    def __init__(self, preferred_engine: str = "piper"):
        self.preferred_engine = preferred_engine
        self._engine = None          # lazy-init
        self._engine_name = None
        self._pyttsx3_engine = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def speak(self, text: str) -> bool:
        """
        Spricht `text` über den Standardlautsprecher aus.
        Gibt True zurück wenn erfolgreich, False bei Fehler.
        """
        if not text or not text.strip():
            logger.warning("TTS: Leerer Text übergeben.")
            return False

        logger.info(f"TTS: '{text[:80]}{'…' if len(text) > 80 else ''}'")

        if self.preferred_engine == "piper" and self._try_piper(text):
            return True

        return self._try_pyttsx3(text)

    def speak_to_file(self, text: str, output_path: str) -> bool:
        """
        Synthetisiert `text` und speichert als WAV-Datei.
        Nützlich für Tests ohne Lautsprecher.
        """
        if not text or not text.strip():
            return False

        if self._try_piper_to_file(text, output_path):
            logger.info(f"TTS → WAV: {output_path}")
            return True

        # Fallback: pyttsx3 → WAV (nur auf macOS/Windows native)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return True
        except Exception as e:
            logger.error(f"TTS speak_to_file fehlgeschlagen: {e}")
            return False

    # ── Piper TTS ──────────────────────────────────────────────────────────────

    def _try_piper(self, text: str) -> bool:
        """Piper via Python-API (piper-tts pip package)."""
        try:
            import sounddevice as sd
            import numpy as np
            import io, wave

            voice = self._get_piper_voice()
            if voice is None:
                return False

            # synthesize_wav → WAV-Bytes → numpy → sounddevice
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # int16
                wf.setframerate(voice.config.sample_rate)
                voice.synthesize(text, wf)

            wav_buffer.seek(0)
            with wave.open(wav_buffer, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            sd.play(audio, samplerate=voice.config.sample_rate, blocking=True)
            self._engine_name = "piper"
            return True

        except ImportError:
            logger.debug("piper-tts nicht installiert, versuche Fallback.")
            return False
        except Exception as e:
            logger.warning(f"Piper TTS Fehler: {e}")
            return False

    def _try_piper_to_file(self, text: str, output_path: str) -> bool:
        """Piper → WAV-Datei."""
        try:
            from piper.voice import PiperVoice
            import wave

            voice = self._get_piper_voice()
            if voice is None:
                return False

            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # int16
                wf.setframerate(voice.config.sample_rate)
                voice.synthesize(text, wf)
            return True
        except Exception:
            return False

    def _get_piper_voice(self):
        """Lädt die Piper-Voice (lazy, gecached)."""
        if self._engine is not None:
            return self._engine
        try:
            from piper.voice import PiperVoice
            # Sucht nach heruntergeladenen Modellen im Home-Verzeichnis
            model_dirs = [
                Path.home() / ".local" / "share" / "piper",
                Path.home() / "piper-models",
                Path("/usr/share/piper"),
            ]
            onnx_file = None
            for d in model_dirs:
                candidates = list(d.glob("de_DE-thorsten*.onnx")) if d.exists() else []
                if candidates:
                    onnx_file = str(candidates[0])
                    break

            if onnx_file is None:
                logger.info(
                    "Piper-Modell nicht gefunden. "
                    "Bitte herunterladen:\n"
                    "  mkdir -p ~/.local/share/piper && cd ~/.local/share/piper\n"
                    "  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                    "de/de_DE/thorsten/high/de_DE-thorsten-high.onnx\n"
                    "  wget https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                    "de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json"
                )
                return None

            self._engine = PiperVoice.load(onnx_file)
            logger.info(f"Piper-Voice geladen: {onnx_file}")
            return self._engine

        except Exception as e:
            logger.warning(f"Piper-Voice konnte nicht geladen werden: {e}")
            return None

    # ── pyttsx3 Fallback ───────────────────────────────────────────────────────

    def _try_pyttsx3(self, text: str) -> bool:
        """Systembasierte TTS als zuverlässiger Fallback."""
        try:
            import pyttsx3
            if self._pyttsx3_engine is None:
                self._pyttsx3_engine = pyttsx3.init()
                # Versuche deutsche Stimme zu setzen
                voices = self._pyttsx3_engine.getProperty("voices")
                for v in voices:
                    if "german" in v.name.lower() or "deutsch" in v.name.lower() or "de_" in v.id.lower():
                        self._pyttsx3_engine.setProperty("voice", v.id)
                        logger.info(f"pyttsx3: deutsche Stimme gewählt: {v.name}")
                        break
                self._pyttsx3_engine.setProperty("rate", 160)  # Sprechrate anpassen

            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()
            self._engine_name = "pyttsx3"
            return True

        except ImportError:
            logger.error("pyttsx3 nicht installiert. pip install pyttsx3")
            return False
        except Exception as e:
            logger.error(f"pyttsx3 Fehler: {e}")
            return False

    @property
    def active_engine(self) -> str:
        return self._engine_name or "unbekannt"
