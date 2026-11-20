"""
talktype/app.py - Main TalkType application orchestrator and system tray manager.
"""

import os
import sys
import time
import threading
import logging
import numpy as np
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot

from talktype.config import load_config, save_config
from talktype.core import (
    AudioRecorder,
    HotkeyListener,
    SoundEffects,
    TextFormatter,
    TextInjector,
    WhisperTranscriber
)
from talktype.ui import FloatingPillHUD, ModernDashboard
from talktype.models import MODEL_CATALOG, is_model_installed
from talktype.state import RuntimePhase, RuntimeStateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TalkType")
MIN_AUDIO_PEAK = 0.001


def create_tray_pixmap(color="#f54e00") -> QPixmap:
    """Draws a compact, high-contrast microphone icon for the system tray."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Rounded brand tile stays distinct at small tray sizes.
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)

    # Mic capsule and stand form a single recognizable silhouette.
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(25, 12, 14, 27, 7, 7)

    stand = QPainterPath()
    stand.moveTo(17, 29)
    stand.lineTo(17, 32)
    stand.cubicTo(17, 41, 23, 47, 32, 47)
    stand.cubicTo(41, 47, 47, 41, 47, 32)
    stand.lineTo(47, 29)
    pen = QPen(QColor("#ffffff"), 4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(stand)
    painter.drawLine(32, 47, 32, 53)
    painter.drawLine(23, 53, 41, 53)
    painter.end()
    return pm


class SignalBridge(QObject):
    """Thread-safe signal bridge between hotkey/audio workers and the PyQt GUI."""
    sig_hold_progress = pyqtSignal(str, float, float)
    sig_recording_started = pyqtSignal()
    sig_transcribing = pyqtSignal(str)
    sig_formatting = pyqtSignal()
    sig_done = pyqtSignal()
    sig_no_speech = pyqtSignal()
    sig_hide = pyqtSignal()
    sig_model_switch_finished = pyqtSignal(str, bool)
    sig_processing_finished = pyqtSignal()


class TalkTypeApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__(qapp)
        self.qapp = qapp
        self.config = load_config()

        # Core Components
        logger.info("Initializing components...")
        self.sounds = SoundEffects(enabled=self.config.get("sound_feedback", True))
        self.recorder = AudioRecorder(sample_rate=self.config.get("sample_rate", 16000))
        self.formatter = TextFormatter()
        self.injector = TextInjector(
            mode=self.config.get("paste_mode", "clipboard"),
            restore_clipboard=self.config.get("restore_clipboard", True)
        )

        # Whisper Model
        self.transcriber = WhisperTranscriber(
            model_size=self.config.get("model_size", "small"),
            device=self.config.get("device", "cpu"),
            compute_type=self.config.get("compute_type", "int8")
        )
        self.config["model_size"] = self.transcriber.model_size
        self.runtime_state = RuntimeStateStore(self.transcriber.model_size)

        # Thread-safe Bridge
        self.bridge = SignalBridge()

        # UI Components: Next-Gen Floating Pill & Studio Dashboard
        self.hud = FloatingPillHUD(
            audio_recorder=self.recorder,
            hotkey_name=self.config.get("hotkey", "ctrl_r"),
            theme=self.config.get("theme", "light")
        )
        self.dashboard = ModernDashboard(
            config=self.config,
            audio_recorder=self.recorder,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        # Connect bridge signals to HUD
        self.bridge.sig_hold_progress.connect(self._render_hold_progress)
        self.bridge.sig_recording_started.connect(self._render_recording)
        self.bridge.sig_transcribing.connect(self._render_transcribing)
        self.bridge.sig_formatting.connect(self._render_formatting)
        self.bridge.sig_done.connect(self._render_done)
        self.bridge.sig_no_speech.connect(self._render_no_speech)
        self.bridge.sig_hide.connect(self._render_hide)
        self.bridge.sig_model_switch_finished.connect(self._on_model_switch_finished)
        self.bridge.sig_processing_finished.connect(self._on_processing_finished)

        # Connect dashboard signals
        self.dashboard.config_updated.connect(self._on_dashboard_config_updated)
        self.dashboard.model_switch_requested.connect(self.switch_model)

        # Global Hotkey Listener
        self.listener = HotkeyListener(
            hotkey_name=self.config.get("hotkey", "ctrl_r"),
            trigger_mode=self.config.get("trigger_mode", "long_press_toggle"),
            long_press_seconds=float(self.config.get("long_press_seconds", 1.0)),
            on_start_recording=self.on_start_recording,
            on_stop_recording=self.on_stop_recording,
            on_hold_progress=self.on_hold_progress,
            on_cancel_hold=self.on_cancel_hold
        )

        self._setup_tray_icon()

    def _setup_tray_icon(self):
        self.tray = QSystemTrayIcon(QIcon(create_tray_pixmap()), self.qapp)
        self.tray.setToolTip("TalkType Voice Typing")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: #26251e;
                border: 1px solid #e6e5e0;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
            QMenu::item {
                padding: 6px 20px 6px 28px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #fafaf7;
                color: #f54e00;
            }
            QMenu::separator {
                height: 1px;
                background-color: #efeee8;
                margin: 4px 8px;
            }
        """)

        # Title
        dur = self.config.get('long_press_seconds', 1.0)
        hk_name = self.config.get('hotkey', 'ctrl_r').upper()
        title_action = menu.addAction(f"⚡ TalkType (Hold {hk_name} {dur:.1f}s)")
        title_action.setEnabled(False)
        menu.addSeparator()

        # Open Studio Dashboard
        dash_action = menu.addAction("🎨 Open TalkType Studio...")
        dash_action.triggered.connect(self.open_dashboard)

        # Pause / Resume
        self.pause_action = menu.addAction("Pause Dictation")
        self.pause_action.triggered.connect(self.toggle_pause)

        menu.addSeparator()

        # Quick Model Submenu
        self.model_menu = menu.addMenu("🧠 Whisper Model")
        self._populate_model_menu()

        menu.addSeparator()

        # Quit
        quit_action = menu.addAction("Exit")
        quit_action.triggered.connect(self.quit_app)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _populate_model_menu(self):
        self.model_menu.clear()
        current_m = self.runtime_state.snapshot().active_model

        for key, info in MODEL_CATALOG.items():
            installed = is_model_installed(key)
            prefix = "✓ " if key == current_m else "    "
            tag = "" if installed else " [Download]"
            name = f"{prefix}{info['name']}{tag}"

            act = self.model_menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(key == current_m)
            act.triggered.connect(lambda checked, k=key: self.switch_model(k))

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_dashboard()

    def open_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def _on_dashboard_config_updated(self, new_config: dict):
        self.config.update(new_config)
        self.dashboard.config = dict(self.config)
        save_config(self.config)

        self.sounds.enabled = self.config.get("sound_feedback", True)
        self.listener.long_press_seconds = float(self.config.get("long_press_seconds", 1.0))
        self.hud.set_hotkey_name(self.config.get("hotkey", "ctrl_r"))
        self.hud.set_theme(self.config.get("theme", "light"))

    @pyqtSlot(str, bool)
    def _on_model_switch_finished(self, model_size: str, success: bool):
        if not self.runtime_state.finish_model_switch(model_size, success):
            logger.warning("Ignoring stale model switch result for '%s'.", model_size)
            return

        active_model = self.runtime_state.snapshot().active_model
        if success:
            self.config["model_size"] = active_model
            save_config(self.config)
            self._populate_model_menu()
            self.dashboard.set_model_switch_state(active_model)
            self._show_model_switched(active_model)
            return

        model_name = MODEL_CATALOG.get(model_size, {}).get("name", model_size)
        active_name = MODEL_CATALOG.get(active_model, {}).get("name", active_model)
        logger.error("Model switch to '%s' failed; keeping '%s' active.", model_size, active_model)
        self.dashboard.set_model_switch_state(
            active_model,
            error=f"Could not load {model_name}. {active_name} is still active; try again or choose another model.",
        )

    def _show_model_switched(self, model_size: str):
        if self.runtime_state.snapshot().phase != RuntimePhase.IDLE:
            return
        self.hud.show_model_switched(model_size.upper())

    @pyqtSlot(str, float, float)
    def _render_hold_progress(self, action: str, elapsed: float, target: float):
        if self.runtime_state.snapshot().phase == RuntimePhase.HOLDING:
            self.hud.show_hold_progress(action, elapsed, target)

    @pyqtSlot()
    def _render_recording(self):
        if self.runtime_state.snapshot().phase == RuntimePhase.RECORDING:
            self.hud.show_recording()

    @pyqtSlot(str)
    def _render_transcribing(self, model_name: str):
        if self.runtime_state.snapshot().phase == RuntimePhase.TRANSCRIBING:
            self.hud.show_transcribing(model_name)

    @pyqtSlot()
    def _render_formatting(self):
        if self.runtime_state.snapshot().phase == RuntimePhase.FORMATTING:
            self.hud.show_formatting()

    @pyqtSlot()
    def _render_done(self):
        # No phase guard — this signal is only emitted by the worker at the correct moment.
        # A phase guard using is_processing would race with sig_processing_finished.
        self.hud.show_done()

    @pyqtSlot()
    def _render_no_speech(self):
        # No phase guard — same reason as _render_done.
        self.hud.show_no_speech()

    @pyqtSlot()
    def _render_hide(self):
        phase = self.runtime_state.snapshot().phase
        if phase not in (RuntimePhase.RECORDING, RuntimePhase.SWITCHING_MODEL):
            self.hud.immediate_hide()

    @pyqtSlot()
    def _on_processing_finished(self):
        if not self.runtime_state.finish_processing():
            logger.warning("Ignoring processing completion outside an active transcription.")

    def switch_model(self, model_size: str):
        state = self.runtime_state.snapshot()
        active_model = state.active_model
        if model_size not in MODEL_CATALOG:
            logger.error("Ignoring unknown speech model selection: %s", model_size)
            self.dashboard.set_model_switch_state(
                active_model, error="That speech model is not available."
            )
            return

        if model_size == active_model and state.phase == RuntimePhase.IDLE:
            self.dashboard.set_model_switch_state(active_model)
            return

        if not self.runtime_state.begin_model_switch(model_size):
            state = self.runtime_state.snapshot()
            if state.phase == RuntimePhase.SWITCHING_MODEL:
                logger.warning(
                    "A model switch to '%s' is already in progress.",
                    state.pending_model,
                )
                return
            logger.warning("Cannot switch models during the %s phase.", state.phase.value)
            self.dashboard.set_model_switch_state(
                state.active_model,
                pending_model=state.pending_model,
                error="Finish the current operation before switching models.",
            )
            return

        state = self.runtime_state.snapshot()
        self.dashboard.set_model_switch_state(
            state.active_model, pending_model=state.pending_model
        )

        def _worker():
            try:
                success = self.transcriber.change_model(model_size)
            except Exception:
                logger.exception("Unexpected error switching to model '%s'.", model_size)
                success = False
            self.bridge.sig_model_switch_finished.emit(model_size, success)

        threading.Thread(target=_worker, daemon=True).start()

    def toggle_pause(self):
        state = self.runtime_state.snapshot()
        paused = not state.paused
        self.runtime_state.set_paused(paused)
        state = self.runtime_state.snapshot()
        self.listener.enabled = not paused

        if paused:
            if state.phase == RuntimePhase.RECORDING:
                self.on_stop_recording()
            elif state.phase == RuntimePhase.HOLDING:
                self.runtime_state.cancel_hold()
                self.bridge.sig_hide.emit()
            self.pause_action.setText("Resume Dictation")
            self.tray.setIcon(QIcon(create_tray_pixmap("#6b7280")))
            self.hud.immediate_hide()
        else:
            self.pause_action.setText("Pause Dictation")
            self.tray.setIcon(QIcon(create_tray_pixmap()))

    # ---- Hotkey / Recording Lifecycle Handlers ----

    def on_hold_progress(self, action: str, elapsed: float, target: float):
        if self.runtime_state.begin_hold():
            self.bridge.sig_hold_progress.emit(action, elapsed, target)

    def on_cancel_hold(self):
        if self.runtime_state.cancel_hold():
            self.bridge.sig_hide.emit()

    def on_start_recording(self):
        if not self.runtime_state.begin_recording():
            if self.runtime_state.snapshot().phase not in (
                RuntimePhase.STARTING_RECORDING,
                RuntimePhase.RECORDING,
            ):
                self.listener.set_recording(False)
            return

        try:
            self.recorder.start()
        except Exception as e:
            self.runtime_state.abort_recording_start()
            self.listener.set_recording(False)
            logger.error(f"Could not start recording: {e}", exc_info=True)
            self.sounds.play_cancel()
            self.bridge.sig_hide.emit()
            return

        stop_requested = self.runtime_state.finish_recording_start()
        logger.info("Recording triggered!")
        self.listener.set_recording(True)
        self.sounds.play_start()
        self.bridge.sig_recording_started.emit()
        if stop_requested:
            self.on_stop_recording()
        if self.runtime_state.snapshot().phase != RuntimePhase.RECORDING:
            self.listener.set_recording(False)

    def on_stop_recording(self):
        if not self.runtime_state.request_stop_recording():
            return

        logger.info("Stop recording triggered. Processing audio...")
        self.listener.set_recording(False)

        threading.Thread(target=self._process_audio_worker, daemon=True).start()

    def _process_audio_worker(self):
        try:
            self.sounds.play_stop()

            # Stop the stream and collect audio FIRST — before showing "Transcribing"
            # so the spinner only appears when we know there's something to transcribe.
            audio_data = self.recorder.stop()
            duration = len(audio_data) / self.config.get("sample_rate", 16000)
            audio_peak = float(np.max(np.abs(audio_data))) if len(audio_data) else 0.0
            audio_rms = float(np.sqrt(np.mean(audio_data ** 2))) if len(audio_data) else 0.0

            # Fast silence bail-out — avoids sending pure-silence to VAD/Whisper entirely
            # which previously caused indefinite hangs when get_speech_timestamps blocked.
            if duration < 0.25 or audio_peak < MIN_AUDIO_PEAK or audio_rms < 0.003:
                logger.info(
                    "No voice detected in recorded audio "
                    f"(duration={duration:.2f}s, peak={audio_peak:.4f}, rms={audio_rms:.4f})."
                )
                self.bridge.sig_no_speech.emit()
                return

            # Only NOW show the transcribing spinner — we know audio has content.
            active_model = self.runtime_state.snapshot().active_model.upper()
            self.bridge.sig_transcribing.emit(active_model)

            t0 = time.time()
            lang = self.config.get("language", "auto")
            prompt = self.config.get("initial_prompt", None)

            raw_text, detected_lang = self.transcriber.transcribe(
                audio_data,
                language=lang,
                initial_prompt=prompt
            )
            transcribe_time = time.time() - t0
            logger.info(f"Transcribed in {transcribe_time:.2f}s: '{raw_text}'")

            if not raw_text.strip():
                logger.info("No speech detected.")
                self.bridge.sig_no_speech.emit()
                return

            # Formatting stage
            if self.config.get("auto_format", True):
                if not self.runtime_state.begin_formatting():
                    raise RuntimeError("Cannot enter formatting outside transcription state.")
                self.bridge.sig_formatting.emit()
                formatted_text = self.formatter.format(raw_text, language=detected_lang)
            else:
                formatted_text = raw_text

            if not formatted_text.strip():
                logger.info("Formatting produced no text; treating the recording as no speech.")
                self.bridge.sig_no_speech.emit()
                return

            # Text Injection stage
            logger.info(f"Injecting text: '{formatted_text}'")
            success = self.injector.inject(formatted_text)

            if success:
                self.sounds.play_success()
                self.bridge.sig_done.emit()
            else:
                self.bridge.sig_hide.emit()

        except Exception as e:
            logger.error(f"Error during audio processing: {e}", exc_info=True)
            self.bridge.sig_hide.emit()
        finally:
            self.bridge.sig_processing_finished.emit()

    def start(self):
        self.listener.start()
        logger.info(f"TalkType is running! Hold {self.listener.hotkey_name.upper()} for ~{self.listener.long_press_seconds}s to start voice typing.")

    def quit_app(self):
        logger.info("Quitting TalkType...")
        self.listener.stop()
        self.hud.immediate_hide()
        self.dashboard.close()
        self.qapp.quit()


def main():
    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    app = TalkTypeApp(qapp)
    app.start()
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
