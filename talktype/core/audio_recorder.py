import numpy as np
import sounddevice as sd
import queue
import threading
import logging

logger = logging.getLogger(__name__)

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, device: int = None):
        self.sample_rate = sample_rate
        self.device = device
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.stream = None
        self._lock = threading.Lock()
        self.latest_volume = 0.0

    def set_device(self, device_index: int):
        """Sets the active input microphone device index."""
        with self._lock:
            self.device = device_index
            logger.info(f"Microphone device set to index: {device_index}")

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice stream to capture microphone chunks."""
        if status:
            logger.warning(f"Audio stream status: {status}")
        if self.is_recording:
            # Measure peak volume for live UI visualizer
            try:
                self.latest_volume = float(np.max(np.abs(indata)))
            except Exception:
                pass
            self.audio_queue.put(indata.copy())

    def get_latest_volume(self) -> float:
        """Returns the latest normalized volume peak (0.0 to 1.0) for live UI animations."""
        if not self.is_recording:
            return 0.0
        return self.latest_volume

    def start(self):
        """Starts capturing audio stream into memory."""
        with self._lock:
            if self.is_recording:
                return
            
            # Clear previous buffer
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            self.is_recording = True
            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    device=self.device,
                    channels=1,
                    dtype='float32',
                    callback=self._audio_callback
                )
                self.stream.start()
                logger.info("Audio recording started.")
            except Exception as e:
                self.is_recording = False
                logger.error(f"Failed to start audio stream: {e}")
                raise

    def stop(self) -> np.ndarray:
        """Stops capturing and returns the recorded audio as a 1D float32 numpy array."""
        with self._lock:
            if not self.is_recording:
                return np.array([], dtype=np.float32)

            self.is_recording = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as e:
                    logger.warning(f"Error stopping stream: {e}")
                self.stream = None

            # Gather all chunks
            chunks = []
            while not self.audio_queue.empty():
                try:
                    chunks.append(self.audio_queue.get_nowait())
                except queue.Empty:
                    break

            if not chunks:
                return np.array([], dtype=np.float32)

            audio_data = np.concatenate(chunks, axis=0).flatten()
            logger.info(f"Recorded {len(audio_data) / self.sample_rate:.2f} seconds of audio.")
            return audio_data
