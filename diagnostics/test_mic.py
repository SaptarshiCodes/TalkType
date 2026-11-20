"""
Quick diagnostics script to test microphone input, volume level, and speech recognition.
Run with: .\venv\Scripts\python.exe test_mic.py
"""

import time
import numpy as np
import sounddevice as sd
from transcriber import WhisperTranscriber
from text_formatter import TextFormatter
import json
import os

print("=" * 60)
print("      TalkType - Microphone & Transcription Diagnostic")
print("=" * 60)

# 1. Load config
config_path = os.path.join(os.path.dirname(__file__), "config.json")
config = {}
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

model_size = config.get("model_size", "small")
lang = config.get("language", "auto")

print(f"\nConfiguration:")
print(f"  - Model: {model_size}")
print(f"  - Target Language: {lang}")
print(f"  - Sample Rate: 16000 Hz")

# 2. Check Input Devices
print("\n[1/3] Default Input Device:")
try:
    dev = sd.query_devices(kind='input')
    print(f"  Name: {dev['name']}")
    print(f"  Max Channels: {dev['max_input_channels']}")
except Exception as e:
    print(f"  Error querying default device: {e}")

# 3. Record test audio
duration = 4.0  # seconds
print(f"\n[2/3] Recording {duration:.0f} seconds of audio...")
print(">>> SPEAK NOW into your microphone in English, Bengali, or Hindi! <<<")

try:
    audio = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype='float32')
    for i in range(int(duration)):
        time.sleep(1)
        print(f"  ... {int(duration) - i}s left")
    sd.wait()
    audio = audio.flatten()
    print("Recording finished.")
except Exception as e:
    print(f"Error during audio recording: {e}")
    exit(1)

# Check audio levels
peak = float(np.max(np.abs(audio)))
rms = float(np.sqrt(np.mean(audio**2)))
print(f"\nAudio Analysis:")
print(f"  - Peak Amplitude: {peak:.4f} (ideal: > 0.10)")
print(f"  - RMS Volume: {rms:.4f}")

if peak < 0.02:
    print("\n[WARNING] Microphone volume is very low! Speak louder or increase microphone volume in Windows Settings.")
else:
    print("  - Signal level is GOOD.")

# 4. Transcribe
print(f"\n[3/3] Loading Whisper model '{model_size}' and transcribing...")
try:
    transcriber = WhisperTranscriber(model_size=model_size)
    formatter = TextFormatter()

    raw_text, detected_lang = transcriber.transcribe(audio, language=lang)
    formatted_text = formatter.format(raw_text, language=detected_lang)

    print("\n" + "=" * 60)
    print("RESULT:")
    print(f"  - Detected Language: {detected_lang}")
    print(f"  - Raw Whisper Output: {repr(raw_text)}")
    print(f"  - Formatted Output:   {repr(formatted_text)}")
    print("=" * 60)

except Exception as e:
    print(f"Error during transcription: {e}")
