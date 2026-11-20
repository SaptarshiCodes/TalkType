import os
import logging
import numpy as np
from faster_whisper import WhisperModel
import threading
from talktype.models.catalog import MODELS_DIR

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._lock = threading.Lock()
        self._load_model()

    def _resolve_model_path(self, model_name: str) -> str:
        """Checks if the model exists in local models/ directory first."""
        local_path = os.path.join(MODELS_DIR, model_name)
        if os.path.exists(local_path) and os.path.isdir(local_path):
            bin_path = os.path.join(local_path, "model.bin")
            if os.path.exists(bin_path) and os.path.getsize(bin_path) > 1000:
                logger.info(f"Using local model from: {local_path}")
                return local_path
        return model_name

    def _load_model(self):
        """Loads or reloads the faster-whisper model."""
        with self._lock:
            resolved_path = self._resolve_model_path(self.model_size)
            logger.info(f"Loading faster-whisper model '{resolved_path}' on {self.device} ({self.compute_type})...")
            try:
                self.model = WhisperModel(
                    resolved_path,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info(f"Model '{self.model_size}' loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load model '{self.model_size}': {e}")
                if self.model_size != "tiny.en":
                    logger.warning("Attempting fallback to 'tiny.en'...")
                    try:
                        self.model = WhisperModel("tiny.en", device=self.device, compute_type=self.compute_type)
                        self.model_size = "tiny.en"
                        logger.info("Fallback to 'tiny.en' succeeded.")
                    except Exception as err:
                        logger.error(f"Fallback failed: {err}")
                        raise
                else:
                    raise

    def change_model(self, model_size: str) -> bool:
        """Switches the model to a different size dynamically and frees old memory."""
        with self._lock:
            if self.model_size == model_size and self.model is not None:
                return True

            logger.info(f"Switching Whisper model from '{self.model_size}' to '{model_size}'...")
            old_model = self.model
            old_size = self.model_size

            try:
                resolved_path = self._resolve_model_path(model_size)
                new_model = WhisperModel(
                    resolved_path,
                    device=self.device,
                    compute_type=self.compute_type
                )
                self.model = new_model
                self.model_size = model_size
                del old_model
                logger.info(f"Successfully switched to model '{model_size}'.")
                return True
            except Exception as e:
                logger.error(f"Failed to switch to model '{model_size}': {e}")
                self.model = old_model
                self.model_size = old_size
                return False

    def transcribe(self, audio_data: np.ndarray, language: str = None, initial_prompt: str = None) -> tuple[str, str]:
        """
        Transcribes numpy audio float32 array.
        Returns:
            tuple[str, str]: (transcribed_text, detected_language)
        """
        with self._lock:
            if self.model is None:
                raise RuntimeError("Whisper model is not loaded.")

            if len(audio_data) == 0:
                return "", "unknown"

            # Auto language handling
            lang = None if language in (None, "auto", "") else language

            try:
                segments, info = self.model.transcribe(
                    audio_data,
                    beam_size=5,
                    language=lang,
                    initial_prompt=initial_prompt,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=400,
                        speech_pad_ms=250
                    )
                )

                text_parts = [segment.text.strip() for segment in segments]
                full_text = " ".join(filter(None, text_parts)).strip()
                detected_lang = info.language if hasattr(info, "language") else "unknown"
                logger.info(f"Transcription complete ({detected_lang}, prob={info.language_probability:.2f}): '{full_text}'")
                return full_text, detected_lang
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                raise
