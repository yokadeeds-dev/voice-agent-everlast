"""
stt.py – Speech-to-Text Wrapper

Verwendet faster-whisper für lokale, CPU-optimierte Transkription.
Unterstützt zwei Eingabemodi:
  1. Mikrofon-Live-Aufnahme (mit automatischer Stille-Erkennung via RMS)
  2. WAV-Datei-Input

Fehlerbehandlung:
  - Leere Transkription  → STTResult.is_empty = True
  - Niedrige Konfidenz   → STTResult.low_confidence = True
  - Hardware-Fehler      → STTResult.error gesetzt
"""

import io
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Konfidenz-Schwellwert: Transkriptionen darunter gelten als unsicher
CONFIDENCE_THRESHOLD = 0.6


@dataclass
class STTResult:
    text: str = ""
    language: str = "de"
    confidence: float = 1.0
    duration_s: float = 0.0
    is_empty: bool = False
    low_confidence: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.is_empty


class SpeechToText:
    """
    Wrapper um faster-whisper.

    Lazy-Loading: Das Whisper-Modell wird erst beim ersten Aufruf geladen,
    damit der Import von stt.py keine Wartezeit verursacht.
    """

    def __init__(self, model_size: str = "base", language: str = "de",
                 device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Lade Whisper-Modell '{self.model_size}' ({self.device}/{self.compute_type}) …")
            t0 = time.time()
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info(f"Whisper geladen in {time.time() - t0:.1f}s")
        except ImportError:
            raise RuntimeError(
                "faster-whisper nicht installiert. "
                "Bitte: pip install faster-whisper"
            )

    # ── Mikrofon-Aufnahme ──────────────────────────────────────────────────────

    def record_from_microphone(
        self,
        sample_rate: int = 16000,
        max_seconds: int = 6,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
    ) -> STTResult:
        """
        Nimmt Audio vom Standardmikrofon auf.
        Beendet die Aufnahme automatisch nach `silence_duration` Sekunden Stille
        oder nach `max_seconds` Sekunden.
        """
        try:
            import sounddevice as sd
        except ImportError:
            return STTResult(error="sounddevice nicht installiert. pip install sounddevice")

        try:
            import scipy.io.wavfile as wav
        except ImportError:
            return STTResult(error="scipy nicht installiert. pip install scipy")

        logger.info("Mikrofon aktiv – bitte sprechen …")
        chunk_size = int(sample_rate * 0.1)  # 100-ms-Chunks
        max_chunks = int(max_seconds / 0.1)
        silence_chunks_needed = int(silence_duration / 0.1)

        frames = []
        silence_count = 0
        recording = True
        chunk_count = 0

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
            while recording and chunk_count < max_chunks:
                chunk, _ = stream.read(chunk_size)
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                frames.append(chunk)
                chunk_count += 1

                if rms < silence_threshold:
                    silence_count += 1
                    if silence_count >= silence_chunks_needed and chunk_count > 10:
                        logger.info("Stille erkannt – Aufnahme beendet.")
                        recording = False
                else:
                    silence_count = 0

        if not frames:
            return STTResult(is_empty=True, error="Keine Audiodaten aufgenommen.")

        audio_array = np.concatenate(frames, axis=0).flatten()
        return self._transcribe_array(audio_array, sample_rate)

    # ── WAV-Datei ──────────────────────────────────────────────────────────────

    SUPPORTED_FORMATS = {".wav", ".mp3", ".flac", ".m4a"}
    FFMPEG_FORMATS   = {".mp3", ".flac", ".m4a"}  # benötigen ffmpeg

    def transcribe_file(self, path: str) -> STTResult:
        """
        Transkribiert eine Audio-Datei.
        WAV: nativ unterstützt.
        MP3/FLAC/M4A: erfordert ffmpeg (winget install ffmpeg / apt install ffmpeg).
        """
        p = Path(path)
        if not p.exists():
            return STTResult(error=f"Datei nicht gefunden: {path}")
        suffix = p.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            return STTResult(error=f"Nicht unterstütztes Format: {suffix}. Erlaubt: {', '.join(sorted(self.SUPPORTED_FORMATS))}")
        if suffix in self.FFMPEG_FORMATS:
            import shutil
            if shutil.which("ffmpeg") is None:
                return STTResult(
                    error=(
                        f"ffmpeg wird für {suffix}-Dateien benötigt, ist aber nicht installiert.\n"
                        "  Windows: winget install ffmpeg\n"
                        "  Linux:   apt install ffmpeg\n"
                        "  Mac:     brew install ffmpeg"
                    )
                )
        return self._transcribe_path(str(p))

    # ── Interne Transkriptions-Logik ───────────────────────────────────────────

    def _transcribe_path(self, path: str) -> STTResult:
        self._load_model()
        t0 = time.time()
        try:
            segments, info = self._model.transcribe(
                path,
                language=self.language,
                beam_size=5,
                vad_filter=True,           # Silero-VAD integriert in faster-whisper
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            return self._build_result(segments, info, time.time() - t0)
        except Exception as e:
            logger.error(f"Transkriptionsfehler: {e}")
            return STTResult(error=str(e))

    def _transcribe_array(self, audio: np.ndarray, sample_rate: int) -> STTResult:
        """Transkribiert ein numpy-Array direkt (kein Zwischen-WAV nötig)."""
        self._load_model()
        t0 = time.time()
        try:
            # faster-whisper akzeptiert float32-Arrays direkt
            segments, info = self._model.transcribe(
                audio,
                language=self.language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            return self._build_result(segments, info, time.time() - t0)
        except Exception as e:
            logger.error(f"Transkriptionsfehler: {e}")
            return STTResult(error=str(e))

    def _build_result(self, segments, info, elapsed: float) -> STTResult:
        """Konsolidiert Segment-Outputs zu einem STTResult."""
        texts = []
        avg_logprob_sum = 0.0
        seg_count = 0

        for seg in segments:
            text = seg.text.strip()
            if text:
                texts.append(text)
            avg_logprob_sum += seg.avg_logprob
            seg_count += 1

        full_text = " ".join(texts).strip()

        if not full_text:
            logger.warning("Leere Transkription.")
            return STTResult(is_empty=True)

        # Konfidenz aus durchschnittlichem Log-Probability schätzen
        # avg_logprob liegt typisch zwischen -1.0 (schlecht) und 0.0 (perfekt)
        avg_logprob = avg_logprob_sum / max(seg_count, 1)
        confidence = float(np.clip(np.exp(avg_logprob), 0.0, 1.0))
        low_confidence = confidence < CONFIDENCE_THRESHOLD

        if low_confidence:
            logger.warning(f"Niedrige STT-Konfidenz: {confidence:.2f} – Text: '{full_text}'")

        logger.info(f"STT ({elapsed:.1f}s): '{full_text}' [conf={confidence:.2f}]")

        return STTResult(
            text=full_text,
            language=info.language if hasattr(info, "language") else self.language,
            confidence=confidence,
            duration_s=elapsed,
            low_confidence=low_confidence,
        )
