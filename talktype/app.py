"""
talktype/app.py - Main TalkType application orchestrator and system tray manager.
"""

import os
import sys
import time
import threading
import logging
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QObject, pyqtSignal

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TalkType")


def create_tray_pixmap(color="#3b82f6") -> QPixmap:
    """Draws a crisp high-DPI circular microphone icon."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Base circle
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)

    # White mic shape
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(26, 16, 12, 20, 6, 6)

    # Stand curve
    pen = painter.pen()
    pen.setColor(QColor("#ffffff"))
    pen.setWidth(3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(20, 24, 24, 20, 0, -180 * 16)
    painter.drawLine(32, 44, 32, 50)
    painter.drawLine(24, 50, 40, 50)
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


class TalkTypeApp:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.config = load_config()
        self.paused = False
        self.is_recording = False
        self.is_processing = False

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

        # Thread-safe Bridge
        self.bridge = SignalBridge()

        # UI Components: Next-Gen Floating Pill & Studio Dashboard
        self.hud = FloatingPillHUD(
            audio_recorder=self.recorder,
            hotkey_name=self.config.get("hotkey", "ctrl_r")
        )
        self.dashboard = ModernDashboard(
            config=self.config,
            audio_recorder=self.recorder,
            transcriber=self.transcriber,
            formatter=self.formatter
        )

        # Connect bridge signals to HUD
        self.bridge.sig_hold_progress.connect(self.hud.show_hold_progress)
        self.bridge.sig_recording_started.connect(self.hud.show_recording)
        self.bridge.sig_transcribing.connect(self.hud.show_transcribing)
        self.bridge.sig_formatting.connect(self.hud.show_formatting)
        self.bridge.sig_done.connect(self.hud.show_done)
        self.bridge.sig_no_speech.connect(self.hud.show_no_speech)
        self.bridge.sig_hide.connect(self.hud.immediate_hide)

        # Connect dashboard signals
        self.dashboard.config_updated.connect(self._on_dashboard_config_updated)
        self.dashboard.model_switched.connect(self._on_dashboard_model_switched)

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
        self.tray = QSystemTrayIcon(QIcon(create_tray_pixmap("#3b82f6")), self.qapp)
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
        current_m = self.config.get("model_size", "small")

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
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_dashboard()

    def open_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def _on_dashboard_config_updated(self, new_config: dict):
        self.config.update(new_config)
        save_config(self.config)

        self.sounds.enabled = self.config.get("sound_feedback", True)
        self.listener.long_press_seconds = float(self.config.get("long_press_seconds", 1.0))
        self.hud.set_hotkey_name(self.config.get("hotkey", "ctrl_r"))

    def _on_dashboard_model_switched(self, new_model_size: str):
        self.config["model_size"] = new_model_size
        save_config(self.config)
        self._populate_model_menu()
        self.hud.show_model_switched(new_model_size.upper())

    def switch_model(self, model_size: str):
        if self.is_recording or self.is_processing:
            logger.warning("Cannot switch models while recording or processing.")
            return

        def _worker():
            success = self.transcriber.change_model(model_size)
            if success:
                self.config["model_size"] = model_size
                save_config(self.config)
                self.dashboard.config["model_size"] = model_size
                self.dashboard.model_switched.emit(model_size)
                self._populate_model_menu()
                self.hud.show_model_switched(model_size.upper())

        threading.Thread(target=_worker, daemon=True).start()

    def toggle_pause(self):
        self.paused = not self.paused
        self.listener.enabled = not self.paused
        if self.paused:
            self.pause_action.setText("Resume Dictation")
            self.tray.setIcon(QIcon(create_tray_pixmap("#6b7280")))
            self.hud.immediate_hide()
        else:
            self.pause_action.setText("Pause Dictation")
            self.tray.setIcon(QIcon(create_tray_pixmap("#3b82f6")))

    # ---- Hotkey / Recording Lifecycle Handlers ----

    def on_hold_progress(self, action: str, elapsed: float, target: float):
        if not self.paused and not self.is_recording and not self.is_processing:
            self.bridge.sig_hold_progress.emit(action, elapsed, target)

    def on_cancel_hold(self):
        if not self.is_recording and not self.is_processing:
            self.bridge.sig_hide.emit()

    def on_start_recording(self):
        if self.paused or self.is_processing:
            return

        logger.info("Recording triggered!")
        self.is_recording = True
        self.sounds.play_start()
        self.recorder.start()
        self.bridge.sig_recording_started.emit()

    def on_stop_recording(self):
        if not self.is_recording:
            return

        logger.info("Stop recording triggered. Processing audio...")
        self.is_recording = False
        self.is_processing = True

        threading.Thread(target=self._process_audio_worker, daemon=True).start()

    def _process_audio_worker(self):
        try:
            self.sounds.play_stop()
            active_model = self.config.get("model_size", "small").upper()
            self.bridge.sig_transcribing.emit(active_model)

            audio_data = self.recorder.stop()
            duration = len(audio_data) / self.config.get("sample_rate", 16000)

            # Skip ultra-short bursts (accidental taps under 0.25s)
            if duration < 0.25 or len(audio_data) == 0:
                logger.info(f"Audio burst too brief ({duration:.2f}s), skipping.")
                self.bridge.sig_no_speech.emit()
                return

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
                self.sounds.play_cancel()
                self.bridge.sig_no_speech.emit()
                return

            # Formatting stage
            if self.config.get("auto_format", True):
                self.bridge.sig_formatting.emit()
                formatted_text = self.formatter.format(raw_text, language=detected_lang)
            else:
                formatted_text = raw_text

            # Text Injection stage
            logger.info(f"Injecting text: '{formatted_text}'")
            success = self.injector.inject(formatted_text)

            if success:
                self.bridge.sig_done.emit()
            else:
                self.sounds.play_cancel()
                self.bridge.sig_hide.emit()

        except Exception as e:
            logger.error(f"Error during audio processing: {e}", exc_info=True)
            self.sounds.play_cancel()
            self.bridge.sig_hide.emit()
        finally:
            self.is_processing = False

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
