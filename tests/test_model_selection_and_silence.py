import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

from talktype.app import TalkTypeApp
from talktype.core.transcriber import WhisperTranscriber
from talktype.models.catalog import MODEL_CATALOG
from talktype.state import RuntimePhase, RuntimeStateStore
from talktype.ui.dashboard import ModernDashboard
from talktype.ui.pill_hud import FloatingPillHUD


class RuntimeStateTests(unittest.TestCase):
    def test_recording_processing_and_model_switch_are_exclusive(self):
        state = RuntimeStateStore("small")

        self.assertTrue(state.begin_hold())
        self.assertFalse(state.begin_model_switch("base"))
        self.assertTrue(state.begin_recording())
        self.assertFalse(state.begin_model_switch("base"))
        self.assertFalse(state.request_stop_recording())
        self.assertTrue(state.finish_recording_start())
        self.assertTrue(state.request_stop_recording())
        self.assertTrue(state.snapshot().is_processing)
        self.assertTrue(state.begin_formatting())
        self.assertTrue(state.finish_processing())

        self.assertTrue(state.begin_model_switch("base"))
        self.assertEqual(state.snapshot().phase, RuntimePhase.SWITCHING_MODEL)
        self.assertFalse(state.begin_recording())
        self.assertTrue(state.finish_model_switch("base", False))
        self.assertEqual(state.snapshot().active_model, "small")
        self.assertTrue(state.begin_model_switch("base"))
        self.assertTrue(state.finish_model_switch("base", True))
        self.assertEqual(state.snapshot().active_model, "base")
        self.assertEqual(state.snapshot().phase, RuntimePhase.IDLE)

    def test_pause_blocks_recording_and_hold_transitions(self):
        state = RuntimeStateStore("small")
        state.set_paused(True)

        self.assertFalse(state.begin_hold())
        self.assertFalse(state.begin_recording())

        state.set_paused(False)
        self.assertTrue(state.begin_recording())

    def test_stop_or_pause_during_start_is_deferred_until_capture_is_ready(self):
        state = RuntimeStateStore("small")
        self.assertTrue(state.begin_recording())
        self.assertFalse(state.request_stop_recording())
        self.assertTrue(state.snapshot().stop_requested)
        self.assertTrue(state.finish_recording_start())
        self.assertTrue(state.request_stop_recording())
        self.assertTrue(state.finish_processing())

        self.assertTrue(state.begin_recording())
        state.set_paused(True)
        self.assertTrue(state.finish_recording_start())
        self.assertTrue(state.request_stop_recording())


class ModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.source_config = {"model_size": "small", "theme": "light"}
        transcriber = SimpleNamespace(model_size="small")
        self.dashboard = ModernDashboard(
            config=self.source_config,
            transcriber=transcriber,
        )

    def tearDown(self):
        self.dashboard.close()
        self.dashboard.deleteLater()
        self.qt_app.processEvents()

    def test_speech_models_are_grouped_by_language(self):
        expected_order = [
            "tiny.en", "base.en", "small.en", "medium.en",
            "bengali.tiny", "bengali", "bengali.medium",
            "hindi.tiny", "hindi", "hindi.medium",
            "tiny", "base", "small", "medium",
        ]
        combo_order = [
            self.dashboard.model_combo.itemData(index)
            for index in range(self.dashboard.model_combo.count())
        ]

        self.assertEqual(list(MODEL_CATALOG), expected_order)
        self.assertEqual(list(self.dashboard.model_card_widgets), expected_order)
        self.assertEqual(combo_order, expected_order)

    def test_switching_back_restores_active_and_selectable_card_states(self):
        self.dashboard.set_model_switch_state("small", pending_model="base")
        self.dashboard.set_model_switch_state("base")

        base = self.dashboard.model_card_widgets["base"]
        small = self.dashboard.model_card_widgets["small"]
        self.assertFalse(base["status"].isHidden())
        self.assertTrue(base["button"].isHidden())
        self.assertTrue(small["status"].isHidden())
        self.assertFalse(small["button"].isHidden())
        self.assertTrue(small["button"].isEnabled())

        self.dashboard.set_model_switch_state("base", pending_model="small")
        self.dashboard.set_model_switch_state("small")

        self.assertEqual(self.dashboard.model_combo.currentData(), "small")
        self.assertFalse(small["status"].isHidden())
        self.assertTrue(small["button"].isHidden())
        self.assertTrue(base["status"].isHidden())
        self.assertFalse(base["button"].isHidden())
        self.assertTrue(base["button"].isEnabled())

    def test_failed_switch_keeps_active_model_and_restores_retry(self):
        self.dashboard.set_model_switch_state("small", pending_model="base")
        base = self.dashboard.model_card_widgets["base"]
        self.assertEqual(base["button"].text(), "Loading...")
        self.assertFalse(base["button"].isEnabled())

        self.dashboard.set_model_switch_state(
            "small",
            error="Could not load Base. Small is still active; try again.",
        )

        self.assertEqual(self.dashboard.model_combo.currentData(), "small")
        self.assertTrue(base["button"].isEnabled())
        self.assertIn("Could not load", self.dashboard.model_state_label.text())

    def test_dashboard_emits_settings_without_mutating_controller_config(self):
        updates = []
        self.dashboard.config_updated.connect(updates.append)
        self.dashboard.config["theme"] = "dark"
        self.dashboard._save()

        self.assertEqual(self.source_config["theme"], "light")
        self.assertEqual(updates, [{"model_size": "small", "theme": "dark"}])


class PillHudMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.hud = FloatingPillHUD(theme="light")

    def tearDown(self):
        self.hud.close()
        self.hud.deleteLater()
        self.qt_app.processEvents()

    def test_completion_message_clears_after_display(self):
        self.hud.show_done()

        QTest.qWait(1200)

        self.assertFalse(self.hud.isVisible())
        self.assertEqual(self.hud.state, "idle")
        self.assertEqual(self.hud.label.text(), "TalkType Ready")

    def test_stale_completion_timer_does_not_hide_a_newer_message(self):
        self.hud.show_done()
        QTest.qWait(450)
        self.hud.show_recording()
        QTest.qWait(100)
        self.hud.show_done()

        QTest.qWait(600)

        self.assertTrue(self.hud.isVisible())
        self.assertEqual(self.hud.label.text(), "Formatted & Pasted")

        QTest.qWait(500)
        self.assertFalse(self.hud.isVisible())


class SilenceDetectionTests(unittest.TestCase):
    def test_vad_rejects_non_speech_without_running_whisper(self):
        transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
        transcriber._lock = threading.Lock()
        transcriber.model = Mock()
        audio = np.zeros(32000, dtype=np.float32)

        with patch(
            "talktype.core.transcriber.get_speech_timestamps",
            return_value=[],
        ):
            result = transcriber.transcribe(audio)

        self.assertEqual(result, ("", "unknown"))
        transcriber.model.transcribe.assert_not_called()

    def test_speech_segments_are_sent_to_whisper_once(self):
        transcriber = WhisperTranscriber.__new__(WhisperTranscriber)
        transcriber._lock = threading.Lock()
        transcriber.model = Mock()
        transcriber.model.transcribe.return_value = (
            [SimpleNamespace(text=" hello ")],
            SimpleNamespace(language="en", language_probability=0.99),
        )

        with patch(
            "talktype.core.transcriber.get_speech_timestamps",
            return_value=[{"start": 1600, "end": 12800}],
        ):
            result = transcriber.transcribe(np.zeros(16000, dtype=np.float32))

        self.assertEqual(result, ("hello", "en"))
        kwargs = transcriber.model.transcribe.call_args.kwargs
        self.assertFalse(kwargs["vad_filter"])
        self.assertEqual(kwargs["clip_timestamps"], [{"start": 0.1, "end": 0.8}])

    def test_empty_transcription_shows_no_speech_and_finishes_processing(self):
        class Signal:
            def __init__(self):
                self.emissions = []

            def emit(self, *args):
                self.emissions.append(args)

        class Sounds:
            def play_stop(self):
                pass

            def play_cancel(self):
                pass

        class Recorder:
            def stop(self):
                audio = np.zeros(32000, dtype=np.float32)
                audio[8000] = 0.01
                return audio

        bridge = SimpleNamespace(
            sig_transcribing=Signal(),
            sig_no_speech=Signal(),
            sig_done=Signal(),
            sig_hide=Signal(),
            sig_processing_finished=Signal(),
        )
        worker = SimpleNamespace(
            sounds=Sounds(),
            config={"model_size": "small", "sample_rate": 16000, "language": "auto"},
            runtime_state=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(active_model="small")
            ),
            bridge=bridge,
            recorder=Recorder(),
            transcriber=SimpleNamespace(
                transcribe=Mock(return_value=("", "unknown"))
            ),
        )

        TalkTypeApp._process_audio_worker(worker)

        self.assertEqual(bridge.sig_no_speech.emissions, [()])
        self.assertEqual(bridge.sig_processing_finished.emissions, [()])
        self.assertEqual(bridge.sig_done.emissions, [])
        self.assertEqual(bridge.sig_hide.emissions, [])


if __name__ == "__main__":
    unittest.main()
