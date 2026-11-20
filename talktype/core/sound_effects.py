import threading
import logging
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

class SoundEffects:
    """
    Synthesizes smooth, luxurious studio acoustic micro-chimes in-memory
    using organic harmonic sine waves and exponential ADSR envelopes.
    Provides instant, delightful physical feedback without harsh PC beeps.
    """
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._sample_rate = 44100
        # Pre-synthesize audio waveforms to ensure zero latency playback
        self._start_wave = self._generate_chime([587.33, 880.00], duration=0.18, decay=10.0, volume=0.22)
        self._stop_wave = self._generate_chime([880.00, 587.33], duration=0.16, decay=12.0, volume=0.20)
        self._success_wave = self._generate_chime([659.25, 880.00, 1174.66], duration=0.26, decay=8.0, volume=0.22)

    def _generate_chime(self, freqs: list[float], duration: float, decay: float, volume: float) -> np.ndarray:
        """Synthesizes smooth harmonic chord with exponential decay envelope."""
        t = np.linspace(0, duration, int(self._sample_rate * duration), endpoint=False)
        output = np.zeros_like(t)

        for i, freq in enumerate(freqs):
            offset_t = i * 0.035
            mask = t >= offset_t
            rel_t = t[mask] - offset_t
            # Smooth 10ms attack curve to eliminate speaker click, followed by organic exponential decay
            attack = 1.0 - np.exp(-rel_t * 90.0)
            envelope = attack * np.exp(-rel_t * decay)
            # Add subtle harmonic overtone (2nd harmonic) for warmth
            tone = np.sin(2 * np.pi * freq * rel_t) + 0.25 * np.sin(2 * np.pi * (freq * 2) * rel_t)
            output[mask] += tone * envelope * (volume / len(freqs))

        return np.ascontiguousarray(output, dtype=np.float32)

    def _play(self, wave: np.ndarray):
        if not self.enabled:
            return
        try:
            sd.play(wave, samplerate=self._sample_rate, blocking=False)
        except Exception as e:
            logger.debug(f"Could not play audio chime: {e}")

    def play_start(self):
        """Warm two-tone ascending bell indicating microphone is active."""
        if self.enabled:
            threading.Thread(target=self._play, args=(self._start_wave,), daemon=True).start()

    def play_stop(self):
        """Soft descending chime indicating recording stopped and transcribing."""
        if self.enabled:
            threading.Thread(target=self._play, args=(self._stop_wave,), daemon=True).start()

    def play_success(self):
        """Pristine 3-tone harmonic confirmation when text is formatted & pasted."""
        if self.enabled:
            threading.Thread(target=self._play, args=(self._success_wave,), daemon=True).start()
