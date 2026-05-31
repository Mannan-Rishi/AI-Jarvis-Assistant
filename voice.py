import os
# Fix for WinError 1114 / Intel MKL Conflict
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import re
import speech_recognition as sr
import edge_tts
import asyncio
import threading
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import io
import ctypes
import tempfile
import time
import config


# ── Single Premium Voice (en-GB-RyanNeural) ──────────────────────────────
_VOICE_PRIMARY  = {'name': 'en-GB-RyanNeural',        'rate': '+8%',  'pitch': '-2Hz'}
_VOICE_FALLBACK = {'name': 'en-US-ChristopherNeural', 'rate': '+8%',  'pitch': '-2Hz'}


def _sanitize_for_tts(text):
    """Strip markdown/formatting symbols so TTS doesn't read them literally."""
    text = re.sub(r'```[\s\S]*?```', '', text)    # fenced code blocks
    text = re.sub(r'`[^`]*`', '', text)            # inline code
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*(.+?)\*', r'\1', text)       # *italic*
    text = re.sub(r'#+\s*', '', text)              # markdown headings
    text = re.sub(r'[-\u2022]\s+', '', text)       # bullet points
    text = re.sub(r'\s+', ' ', text)               # collapse extra whitespace
    return text.strip()


class VoiceEngine:
    def __init__(self):
        self.is_speaking = False
        self.lock = threading.Lock()
        self.mci = ctypes.windll.winmm
        self.energy_threshold = 500

        # Interruption support
        self.on_interrupt = None
        self._monitor_active = False     # guard: only one monitor at a time
        # Event set when stop_speech() is called — cancels both synthesis-in-progress
        # and the non-blocking playback poll loop.
        self._cancel_speak = threading.Event()

        # Pre-compute temp file paths to avoid repeated tempfile.gettempdir() calls.
        # Double-buffered: alternate between two files so a new synthesis can
        # start while the previous file is still being played.
        _tmp = tempfile.gettempdir()
        self._temp_files = [
            os.path.join(_tmp, "jv_a.mp3"),
            os.path.join(_tmp, "jv_b.mp3"),
        ]
        self._buf_idx = 0

        # Persistent asyncio event loop in a dedicated daemon thread.
        # Eliminates the ~80ms overhead of asyncio.run() creating a fresh loop each call.
        self._loop = asyncio.new_event_loop()
        threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="jarvis-tts-loop"
        ).start()

        # Lazy-load Whisper to prevent startup crashes
        self.whisper_model = None
        self.use_fallback = False
        threading.Thread(target=self._init_whisper, daemon=True).start()

        # Passive Mode State
        self.passive_mode_active = False
        self._pause_passive = False
        self.wake_callback = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _monitor_for_interrupt(self):
        """
        Lightweight background mic monitor — active only while JARVIS is speaking.
        Reads 100 ms chunks; if voice energy (RMS) exceeds threshold, immediately
        kills playback and fires on_interrupt callback.
        """
        if self._monitor_active:
            return                        # prevent overlapping monitors
        self._monitor_active = True
        fs = 16000
        chunk_samples = int(0.1 * fs)    # 100 ms — responsive but not CPU-heavy
        try:
            with sd.InputStream(samplerate=fs, channels=1, dtype='int16') as stream:
                while self.is_speaking:
                    chunk, _ = stream.read(chunk_samples)
                    rms = np.sqrt(np.mean(chunk.astype(float) ** 2))
                    if rms > self.energy_threshold:
                        print("--> JARVIS: [INTERRUPT] Voice detected — killing playback.")
                        self.stop_speech()        # instant MCI kill
                        if callable(self.on_interrupt):
                            threading.Thread(
                                target=self.on_interrupt,
                                daemon=True,
                                name="jarvis-interrupt-handler"
                            ).start()
                        break
        except Exception as e:
            print(f"--> JARVIS: [INTERRUPT] Monitor error: {e}")
        finally:
            self._monitor_active = False

    def _init_whisper(self):
        """Attempts to load Whisper locally, falls back to Google on failure."""
        try:
            from faster_whisper import WhisperModel
            print(f"--> JARVIS: Loading Speech Model ({config.WHISPER_MODEL})...")
            self.whisper_model = WhisperModel(
                config.WHISPER_MODEL,
                device=config.WHISPER_DEVICE,
                compute_type="int8"
            )
            print("--> JARVIS: Neural Link Established.")
        except Exception as e:
            print(f"--> JARVIS: Local AI Ear failed to load ({e}). Using Cloud Fallback.")
            self.use_fallback = True

    def _generate_tts(self, text, out_file, voice_name, rate='+0%', pitch='+0Hz'):
        """
        Run edge-tts synthesis on the persistent event loop.
        Accepts voice name + prosody params for bilingual support.
        """
        async def _run():
            communicate = edge_tts.Communicate(
                text, voice_name, rate=rate, pitch=pitch
            )
            await communicate.save(out_file)

        future = asyncio.run_coroutine_threadsafe(_run(), self._loop)
        future.result()   # blocks calling thread until audio is ready

    # ------------------------------------------------------------------
    # Public API & Passive Listener
    # ------------------------------------------------------------------

    def _passive_listen_loop(self):
        """Burst-listening engine for wake word detection."""
        fs = 16000
        chunk_duration = 0.1
        chunk_samples = int(chunk_duration * fs)
        burst_duration = 1.5  # Record 1.5s burst
        burst_samples = int(burst_duration * fs)
        
        passive_energy_threshold = self.energy_threshold - 100  # More sensitive

        print(f"--> JARVIS: [PASSIVE] Background listener initialized (threshold={passive_energy_threshold}).")

        while self.passive_mode_active:
            if self.is_speaking or self._pause_passive:
                time.sleep(0.1)
                continue

            try:
                with sd.InputStream(samplerate=fs, channels=1, dtype='int16') as stream:
                    triggered = False
                    # Wait for energy spike
                    while self.passive_mode_active and not (self.is_speaking or self._pause_passive):
                        chunk, _ = stream.read(chunk_samples)
                        rms = np.sqrt(np.mean(chunk.astype(float) ** 2))
                        if rms > passive_energy_threshold:
                            print(f"--> JARVIS: [PASSIVE] RMS spike detected: {rms:.1f}")
                            triggered = True
                            break

                    if not triggered:
                        continue

                    print("--> JARVIS: [PASSIVE] Capturing 1.5s audio burst...")
                    # High energy detected -> record a quick burst
                    audio_data_list = [chunk]
                    remaining_chunks = int(burst_samples / chunk_samples) - 1
                    for _ in range(remaining_chunks):
                        if self.is_speaking or self._pause_passive:
                            print("--> JARVIS: [PASSIVE] Burst interrupted.")
                            break
                        chunk, _ = stream.read(chunk_samples)
                        audio_data_list.append(chunk)

                    if self.is_speaking or self._pause_passive:
                        continue

                    # Verify wake word
                    recording = np.concatenate(audio_data_list)
                    
                    text = ""
                    if self.whisper_model and not self.use_fallback:
                        print("--> JARVIS: [PASSIVE] Sending burst to Local AI (faster-whisper)...")
                        audio_fp32 = recording.flatten().astype(np.float32) / 32768.0
                        segments, info = self.whisper_model.transcribe(audio_fp32, beam_size=5, language="en", condition_on_previous_text=False)
                        text = " ".join([s.text for s in segments]).strip().lower()
                    else:
                        print("--> JARVIS: [PASSIVE] Sending burst to Cloud Fallback...")
                        recognizer = sr.Recognizer()
                        byte_io = io.BytesIO()
                        wav.write(byte_io, fs, recording)
                        byte_io.seek(0)
                        with sr.AudioFile(byte_io) as source:
                            audio_data = recognizer.record(source)
                        try:
                            text = recognizer.recognize_google(audio_data).lower()
                        except Exception:
                            pass
                            
                    print(f"--> JARVIS: [PASSIVE] Transcription result: '{text}'")

                    wake_words = ["jarvis", "jarwis", "jarvez", "wake up"]
                    if any(ww in text for ww in wake_words):
                        print(f"--> JARVIS: [PASSIVE] Wake Word Matched! Triggering callback...")
                        if callable(self.wake_callback):
                            self.wake_callback()
                            time.sleep(2) # Pause to let main thread take over
                            
            except Exception as e:
                print(f"--> JARVIS: [PASSIVE] Listener error: {e}")
                time.sleep(1)

    def start_passive_listening(self, callback):
        print("--> JARVIS: [DEBUG] Calling start_passive_listening...")
        self.wake_callback = callback
        if not self.passive_mode_active:
            self.passive_mode_active = True
            threading.Thread(target=self._passive_listen_loop, daemon=True, name="jarvis-passive-listener").start()

    def stop_speech(self):
        """Instantly stops MCI playback and signals any in-progress speak thread."""
        print("--> JARVIS: [STOP] Killing active speech playback.")
        self._cancel_speak.set()          # signals poll loop and synthesis check to abort
        self.mci.mciSendStringW("stop j_audio", None, 0, 0)
        self.mci.mciSendStringW("close j_audio", None, 0, 0)
        self.is_speaking = False

    def speak(self, text):
        """Synthesizes text with auto-selected bilingual voice and plays via MCI."""
        if not text:
            return

        text = _sanitize_for_tts(text)
        if not text:
            return

        # Always use the single premium voice
        voice_cfg = _VOICE_PRIMARY
        print(f"--> JARVIS: [VOICE] {voice_cfg['name']} (rate={voice_cfg['rate']} pitch={voice_cfg['pitch']})")

        def _speak_thread():
            self._cancel_speak.clear()
            self._buf_idx = (self._buf_idx + 1) % 2
            out_file = self._temp_files[self._buf_idx]

            # Synthesize with selected voice; fall back to Christopher if it fails
            try:
                self._generate_tts(
                    text, out_file,
                    voice_cfg['name'], voice_cfg['rate'], voice_cfg['pitch']
                )
            except Exception as e:
                print(f"--> JARVIS: [VOICE] Primary voice failed ({e}), trying fallback.")
                try:
                    self._generate_tts(
                        text, out_file,
                        _VOICE_FALLBACK['name'],
                        _VOICE_FALLBACK['rate'],
                        _VOICE_FALLBACK['pitch']
                    )
                except Exception as e2:
                    print(f"--> TTS Generation Error: {e2}")
                    return

            if self._cancel_speak.is_set():
                print("--> JARVIS: [STOP] Speech cancelled before playback (interrupted during synthesis).")
                return

            with self.lock:
                self.mci.mciSendStringW("stop j_audio", None, 0, 0)
                self.mci.mciSendStringW("close j_audio", None, 0, 0)
                self.is_speaking = True

                threading.Thread(
                    target=self._monitor_for_interrupt,
                    daemon=True,
                    name="jarvis-interrupt-monitor"
                ).start()

                try:
                    if os.path.exists(out_file) and not self._cancel_speak.is_set():
                        self.mci.mciSendStringW(
                            f'open "{out_file}" type mpegvideo alias j_audio',
                            None, 0, 0
                        )
                        self.mci.mciSendStringW("play j_audio", None, 0, 0)
                        print("--> JARVIS: [PLAY] Playback started (non-blocking).")

                        while self.is_speaking and not self._cancel_speak.is_set():
                            status_buf = ctypes.create_unicode_buffer(128)
                            self.mci.mciSendStringW(
                                "status j_audio mode", status_buf, 128, 0
                            )
                            if status_buf.value in ("stopped", ""):
                                print("--> JARVIS: [PLAY] Playback finished naturally.")
                                break
                            time.sleep(0.05)

                        self.mci.mciSendStringW("stop j_audio", None, 0, 0)
                        self.mci.mciSendStringW("close j_audio", None, 0, 0)

                        if self._cancel_speak.is_set():
                            print("--> JARVIS: [STOP] Playback interrupted and cleaned up.")

                except Exception as e:
                    print(f"--> TTS Playback Error: {e}")
                finally:
                    self.is_speaking = False

        threading.Thread(target=_speak_thread, daemon=True).start()

    def listen(self, timeout=10):
        """Dual-engine listening: Uses Whisper locally or Google as fallback."""
        self._pause_passive = True
        try:
            fs = 16000
            print("--> JARVIS: Listening...")

            audio_data_list = []
            speech_started = False
            silent_chunks = 0

            chunk_duration = 0.2
            chunk_samples = int(chunk_duration * fs)
            max_chunks = int(timeout / chunk_duration)

            with sd.InputStream(samplerate=fs, channels=1, dtype='int16') as stream:
                for _ in range(max_chunks):
                    chunk, _ = stream.read(chunk_samples)
                    audio_data_list.append(chunk)

                    rms = np.sqrt(np.mean(chunk.astype(float) ** 2))
                    if rms > self.energy_threshold:
                        speech_started = True
                        silent_chunks = 0
                    elif speech_started:
                        silent_chunks += 1

                    if speech_started and silent_chunks > 4:  # ~0.8 s silence
                        break

            if not speech_started:
                return "..."

            recording = np.concatenate(audio_data_list)

            # Engine selection
            if self.whisper_model and not self.use_fallback:
                # 1. Faster-Whisper Local Processing
                print("--> JARVIS: Processing (Local AI)...")
                audio_fp32 = recording.flatten().astype(np.float32) / 32768.0
                segments, info = self.whisper_model.transcribe(audio_fp32, beam_size=5)
                text = " ".join([s.text for s in segments]).strip()
                if text:
                    print(f"--> Decoded ({info.language}): {text}")
                    return text.lower()
            else:
                # 2. Google Cloud Fallback (Stable)
                print("--> JARVIS: Processing (Cloud Fallback)...")
                recognizer = sr.Recognizer()
                byte_io = io.BytesIO()
                wav.write(byte_io, fs, recording)
                byte_io.seek(0)
                with sr.AudioFile(byte_io) as source:
                    audio_data = recognizer.record(source)

                # Try English first, then Urdu
                try:
                    text = recognizer.recognize_google(audio_data)
                except Exception:
                    text = recognizer.recognize_google(audio_data, language='ur-PK')

                if text:
                    print(f"--> Decoded (Fallback): {text}")
                    return text.lower()

            return "..."

        except Exception as e:
            print(f"Voice Error: {e}")
            return None
        finally:
            self._pause_passive = False


# Global instance
voice = VoiceEngine()
