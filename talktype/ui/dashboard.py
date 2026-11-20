"""
dashboard.py - Studio Control Center for TalkType.
Designed strictly following Cursor's Design System (.agents/skills/design/cursor-design.md):
- Editorial calm over IDE-darkness: warm cream floor (#f7f7f4), warm near-black ink (#26251e).
- Single brand voltage: Cursor Orange (#f54e00) used with disciplined restraint.
- Display weight stays at 400 with negative letter-spacing — magazine-editorial voice.
- Hairline-only depth (1px #e6e5e0); zero drop shadows.
- JetBrains Mono / monospace on every code, keycap, and numerical telemetry surface.
- AI-timeline pastel pill tokens for model dialects (peach, mint, blue, lavender, gold).
"""

import sys
import os
import json
import time
import math
import numpy as np
import sounddevice as sd
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QTextEdit, QFrame, QScrollArea,
    QStackedWidget, QButtonGroup, QAbstractButton, QSizePolicy
)
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QLinearGradient, QPen, QPainterPath

from talktype.models.catalog import MODEL_CATALOG, is_model_installed, download_model_in_background
from talktype.config import CONFIG_PATH
from talktype.ui.motion import AnimatedStackedWidget, SpringDamper


class CursorVUMeter(QWidget):
    """
    Sleek, continuous modern audio level meter following Cursor editorial guidelines.
    Replaces dated blocky chunks with a clean linear fluid gradient track and
    a crisp hairline peak-hold needle.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self.level = 0.0
        self.peak = 0.0
        self.peak_decay = 0.0

    def set_level(self, lvl: float):
        self.level = max(0.0, min(1.0, lvl))
        if self.level > self.peak:
            self.peak = self.level
            self.peak_decay = 0.0
        else:
            self.peak_decay += 0.03
            self.peak = max(0.0, self.peak - self.peak_decay * 0.04)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        r = h / 2.0

        # Background track: soft warm hairline cream
        painter.setPen(QPen(QColor("#e6e5e0"), 1.0))
        painter.setBrush(QBrush(QColor("#efeee8")))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # Active fill: subtle mint to warm amber to Cursor Orange at peak
        if self.level > 0.01:
            active_w = max(h, w * self.level)
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor("#9fc9a2"))  # Mint (Cursor Grep)
            grad.setColorAt(0.65, QColor("#dfa88f")) # Peach (Cursor Thinking)
            grad.setColorAt(0.95, QColor("#f54e00")) # Cursor Orange

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(0.5, 0.5, active_w - 1.0, h - 1.0), r, r)

        # Hairline peak needle
        if self.peak > 0.03:
            peak_x = min(w - 2.5, max(r, w * self.peak))
            painter.setPen(QPen(QColor("#26251e"), 1.6))
            painter.drawLine(int(peak_x), 1, int(peak_x), h - 1)


class CursorToggleSwitch(QAbstractButton):
    """
    Tactile, minimalist toggle switch adhering to Cursor's 8px/pill radius scale.
    Warm cream/hairline off-state with signature Cursor Orange (#f54e00) active state.
    """
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(38, 22)
        self._thumb_pos = 19.0 if checked else 3.0
        self._anim = QPropertyAnimation(self, b"thumb_pos", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._on_toggled)

    def get_thumb_pos(self) -> float:
        return self._thumb_pos

    def set_thumb_pos(self, pos: float):
        self._thumb_pos = pos
        self.update()

    thumb_pos = pyqtProperty(float, get_thumb_pos, set_thumb_pos)

    def _on_toggled(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(19.0 if checked else 3.0)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        r = h / 2.0

        # Background track
        if self.isChecked():
            track_color = QColor("#f54e00")  # Cursor Orange
            border_color = QColor("#d04200")
        else:
            track_color = QColor("#e6e5e0")  # Surface Strong
            border_color = QColor("#cfcdc4")

        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), r, r)

        # Sliding circular thumb
        thumb_d = 16.0
        thumb_y = 3.0
        painter.setPen(QPen(QColor(0, 0, 0, 18), 1.0))
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QRectF(self._thumb_pos, thumb_y, thumb_d, thumb_d))


class ModernDashboard(QWidget):
    """
    TalkType Studio Control Center.
    Designed strictly according to Cursor's developer-brand editorial aesthetic:
    - Quietly-confident warm cream (#f7f7f4) base canvas.
    - Warm near-black ink (#26251e) typography with 400 weight display.
    - Hairline depth only (1px #e6e5e0); no drop shadows.
    - Signature Cursor Orange (#f54e00) primary CTAs.
    - AI-timeline pastel pill palette for model language dialects.
    """
    config_updated = pyqtSignal(dict)
    model_switched = pyqtSignal(str)

    def __init__(self, config: dict, audio_recorder=None, transcriber=None, formatter=None):
        super().__init__()
        self.config = config
        self.audio_recorder = audio_recorder
        self.transcriber = transcriber
        self.formatter = formatter
        self.is_test_recording = False

        self._init_window()
        self._init_ui()
        self._init_mic_meter()

    def _init_window(self):
        self.setWindowTitle("TalkType Studio")
        self.resize(640, 780)
        self.setStyleSheet("""
            QWidget {
                background-color: #f7f7f4;
                color: #26251e;
                font-family: 'Inter', 'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif;
            }
            QFrame#card {
                background-color: #ffffff;
                border: 1px solid #e6e5e0;
                border-radius: 12px;
                padding: 16px;
            }
            QFrame#card:hover {
                border-color: #cfcdc4;
            }
            QLabel#sectionHeader {
                color: #807d72;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.88px;
                text-transform: uppercase;
                background: transparent;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e6e5e0;
                border-radius: 8px;
                padding: 8px 12px;
                color: #26251e;
                font-size: 13px;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #cfcdc4;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #e6e5e0;
                selection-background-color: #f7f7f4;
                selection-color: #f54e00;
                color: #26251e;
                padding: 4px;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cfcdc4;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
                color: #26251e;
            }
            QPushButton:hover {
                background-color: #fafaf7;
                border-color: #a09c92;
            }
            QPushButton:pressed {
                background-color: #efeee8;
            }
            QPushButton#primaryBtn {
                background-color: #f54e00;
                border: 1px solid #d04200;
                color: #ffffff;
                font-weight: 500;
            }
            QPushButton#primaryBtn:hover {
                background-color: #d04200;
                border-color: #b03800;
            }
            QPushButton#tabBtn {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
                color: #5a5852;
            }
            QPushButton#tabBtn:hover {
                color: #26251e;
                background-color: rgba(255, 255, 255, 0.5);
            }
            QPushButton#tabBtn:checked {
                background-color: #ffffff;
                color: #26251e;
                font-weight: 600;
                border: 1px solid #cfcdc4;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #e6e5e0;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #26251e;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 16px;
                height: 16px;
                margin-top: -6px;
                margin-bottom: -6px;
                border-radius: 8px;
                border: 2px solid #26251e;
            }
            QSlider::handle:horizontal:hover {
                border-color: #f54e00;
            }
            QTextEdit {
                background-color: #fafaf7;
                border: 1px solid #e6e5e0;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                color: #26251e;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border-color: #f54e00;
                background-color: #ffffff;
            }
            QScrollBar:vertical {
                border: none;
                background: #f7f7f4;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #e6e5e0;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #cfcdc4;
            }
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        # 1. Header Bar (Editorial Magazine voice)
        header = QHBoxLayout()
        header.setSpacing(12)

        # Brand Mark: Cursor Orange square with crisp white 'T'
        brand_icon = QLabel("T", self)
        brand_icon.setFixedSize(30, 30)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_icon.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        brand_icon.setStyleSheet("""
            background-color: #f54e00;
            color: #ffffff;
            border-radius: 7px;
        """)
        header.addWidget(brand_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)

        # Display weight 400 with negative letter-spacing
        title_label = QLabel("TalkType Studio", self)
        title_font = QFont("Inter", 16)
        title_font.setWeight(QFont.Weight.Normal)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, -0.4)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #26251e; background: transparent;")

        sub_label = QLabel("Local Voice Typing Engine • 14 Offline Models", self)
        sub_font = QFont("Inter", 9)
        sub_label.setFont(sub_font)
        sub_label.setStyleSheet("color: #807d72; background: transparent;")
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(sub_label)
        header.addLayout(title_vbox)

        header.addStretch()

        # Active Model Pill Badge: Mint pastel (Cursor Grep token)
        current_m = self.config.get("model_size", "small").upper()
        self.status_pill = QLabel(f"● {current_m} (CPU int8)", self)
        self.status_pill.setFont(QFont("JetBrains Mono", 9, QFont.Weight.Medium))
        self.status_pill.setStyleSheet("""
            background-color: #eff7f0;
            color: #1f6d2b;
            border: 1px solid #bfe4c4;
            border-radius: 9999px;
            padding: 4px 12px;
        """)
        header.addWidget(self.status_pill)
        main_layout.addLayout(header)

        # 2. Segmented Tab Bar (Clean, no emojis)
        tab_bar_frame = QFrame()
        tab_bar_frame.setStyleSheet("""
            background-color: #efeee8;
            border: 1px solid #cfcdc4;
            border-radius: 8px;
            padding: 2px;
        """)
        tab_layout = QHBoxLayout(tab_bar_frame)
        tab_layout.setContentsMargins(2, 2, 2, 2)
        tab_layout.setSpacing(2)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.btn_tab_audio = QPushButton("Audio && Trigger")
        self.btn_tab_audio.setObjectName("tabBtn")
        self.btn_tab_audio.setCheckable(True)
        self.btn_tab_audio.setChecked(True)

        self.btn_tab_models = QPushButton("Speech Models")
        self.btn_tab_models.setObjectName("tabBtn")
        self.btn_tab_models.setCheckable(True)

        self.btn_tab_test = QPushButton("Playground")
        self.btn_tab_test.setObjectName("tabBtn")
        self.btn_tab_test.setCheckable(True)

        self.tab_group.addButton(self.btn_tab_audio, 0)
        self.tab_group.addButton(self.btn_tab_models, 1)
        self.tab_group.addButton(self.btn_tab_test, 2)
        self.tab_group.idClicked.connect(self._on_tab_clicked)

        tab_layout.addWidget(self.btn_tab_audio)
        tab_layout.addWidget(self.btn_tab_models)
        tab_layout.addWidget(self.btn_tab_test)
        main_layout.addWidget(tab_bar_frame)

        # 3. Stacked Pages with Fluid Motion Transitions
        self.stack = AnimatedStackedWidget(self)
        self.stack.addWidget(self._build_audio_page())
        self.stack.addWidget(self._build_models_page())
        self.stack.addWidget(self._build_playground_page())
        main_layout.addWidget(self.stack, 1)

    def _on_tab_clicked(self, idx: int):
        self.stack.slide_to_index(idx)
        self.btn_tab_audio.setChecked(idx == 0)
        self.btn_tab_models.setChecked(idx == 1)
        self.btn_tab_test.setChecked(idx == 2)

    # ---------------- PAGE 1: Audio & Trigger ----------------
    def _build_audio_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(14)

        # Card 1: Input Device & Live VU Meter
        card_mic = QFrame()
        card_mic.setObjectName("card")
        c_layout = QVBoxLayout(card_mic)
        c_layout.setSpacing(12)

        c_layout.addWidget(self._make_header("MICROPHONE INPUT"))

        self.dev_combo = QComboBox()
        self._populate_audio_devices()
        self.dev_combo.currentIndexChanged.connect(self._on_device_changed)
        c_layout.addWidget(self.dev_combo)

        # VU Meter Container
        vu_box = QVBoxLayout()
        vu_box.setSpacing(6)
        vu_header = QHBoxLayout()
        vu_title = QLabel("Signal Level", self)
        vu_title.setStyleSheet("color: #807d72; font-size: 11px; background: transparent;")
        self.vu_db_label = QLabel("-∞ dB", self)
        self.vu_db_label.setStyleSheet("color: #807d72; font-size: 11px; font-family: 'JetBrains Mono', Consolas, monospace; background: transparent;")
        vu_header.addWidget(vu_title)
        vu_header.addStretch()
        vu_header.addWidget(self.vu_db_label)
        vu_box.addLayout(vu_header)

        self.vu_meter = CursorVUMeter(self)
        vu_box.addWidget(self.vu_meter)
        c_layout.addLayout(vu_box)

        layout.addWidget(card_mic)

        # Card 2: Activation & Trigger Hotkey
        card_trig = QFrame()
        card_trig.setObjectName("card")
        t_layout = QVBoxLayout(card_trig)
        t_layout.setSpacing(12)

        t_layout.addWidget(self._make_header("ACTIVATION & TOGGLE TIMING"))

        # Hotkey Keycap Display
        h_row = QHBoxLayout()
        h_lbl = QLabel("Activation Hotkey:", self)
        h_lbl.setStyleSheet("color: #5a5852; font-size: 13px; font-weight: 500; background: transparent;")
        current_hk = self.config.get("hotkey", "ctrl_r")
        hk_names = {
            "ctrl_r": "Right Control  [ctrl_r]",
            "ctrl_l": "Left Control  [ctrl_l]",
            "tab": "Tab  [tab]"
        }
        disp_name = hk_names.get(current_hk, f"{current_hk.upper()}  [{current_hk}]")
        self.hotkey_badge = QLabel(disp_name, self)
        self.hotkey_badge.setStyleSheet("""
            background-color: #fafaf7;
            color: #26251e;
            border: 1px solid #cfcdc4;
            border-radius: 6px;
            padding: 4px 10px;
            font-family: 'JetBrains Mono', Consolas, monospace;
            font-weight: 600;
            font-size: 11.5px;
        """)
        h_row.addWidget(h_lbl)
        h_row.addStretch()
        h_row.addWidget(self.hotkey_badge)
        t_layout.addLayout(h_row)

        # Hold Duration Slider
        dur_vbox = QVBoxLayout()
        dur_vbox.setSpacing(6)
        dur_header = QHBoxLayout()
        dur_title = QLabel("Hold to Start Duration:", self)
        dur_title.setStyleSheet("color: #5a5852; font-size: 13px; font-weight: 500; background: transparent;")
        current_dur = self.config.get("long_press_seconds", 1.0)
        self.duration_val_lbl = QLabel(f"{current_dur:.1f}s", self)
        self.duration_val_lbl.setStyleSheet("color: #f54e00; font-family: 'JetBrains Mono', Consolas, monospace; font-weight: 600; font-size: 12px; background: transparent;")
        dur_header.addWidget(dur_title)
        dur_header.addStretch()
        dur_header.addWidget(self.duration_val_lbl)
        dur_vbox.addLayout(dur_header)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(8, 30)
        self.slider.setValue(int(current_dur * 10))
        self.slider.valueChanged.connect(self._on_slider_changed)
        dur_vbox.addWidget(self.slider)

        subtext = QLabel(f"Hold {disp_name.split()[0]} for this duration to start. Tap once to stop & paste.", self)
        subtext.setStyleSheet("color: #807d72; font-size: 11.5px; background: transparent;")
        subtext.setWordWrap(True)
        dur_vbox.addWidget(subtext)
        t_layout.addLayout(dur_vbox)

        layout.addWidget(card_trig)

        # Card 3: Formatting & System Options (Tactile Toggle Switches)
        card_opts = QFrame()
        card_opts.setObjectName("card")
        o_layout = QVBoxLayout(card_opts)
        o_layout.setSpacing(14)

        o_layout.addWidget(self._make_header("PREFERENCES & AUTOMATION"))

        # Language dropdown
        l_row = QHBoxLayout()
        l_lbl = QLabel("Dictation Language:", self)
        l_lbl.setStyleSheet("color: #5a5852; font-size: 13px; font-weight: 500; background: transparent;")
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto-Detect (English, Bengali, Hindi...)", "auto")
        self.lang_combo.addItem("English (en)", "en")
        self.lang_combo.addItem("Bengali / বাংলা (bn)", "bn")
        self.lang_combo.addItem("Hindi / हिन्दी (hi)", "hi")
        current_lang = self.config.get("language", "auto")
        l_idx = self.lang_combo.findData(current_lang)
        if l_idx >= 0:
            self.lang_combo.setCurrentIndex(l_idx)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        l_row.addWidget(l_lbl)
        l_row.addWidget(self.lang_combo, 1)
        o_layout.addLayout(l_row)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #efeee8; border: none; max-height: 1px;")
        o_layout.addWidget(sep)

        # Toggle 1: Smart Formatting
        row_fmt = QHBoxLayout()
        fmt_text_vbox = QVBoxLayout()
        fmt_title = QLabel("Spoken Punctuation & Formatting", self)
        fmt_title.setStyleSheet("color: #26251e; font-size: 13px; font-weight: 500; background: transparent;")
        fmt_desc = QLabel("Auto-capitalizes sentences and formats spoken commands ('comma', 'period', 'new line')", self)
        fmt_desc.setStyleSheet("color: #807d72; font-size: 11.5px; background: transparent;")
        fmt_text_vbox.addWidget(fmt_title)
        fmt_text_vbox.addWidget(fmt_desc)
        row_fmt.addLayout(fmt_text_vbox, 1)

        self.sw_format = CursorToggleSwitch(checked=self.config.get("auto_format", True), parent=self)
        self.sw_format.toggled.connect(self._on_format_sw_toggled)
        row_fmt.addWidget(self.sw_format)
        o_layout.addLayout(row_fmt)

        # Toggle 2: Acoustic Feedback Chimes
        row_snd = QHBoxLayout()
        snd_text_vbox = QVBoxLayout()
        snd_title = QLabel("Acoustic Micro-Chimes", self)
        snd_title.setStyleSheet("color: #26251e; font-size: 13px; font-weight: 500; background: transparent;")
        snd_desc = QLabel("Plays subtle non-intrusive sound cues on dictation start, finish, and cancel", self)
        snd_desc.setStyleSheet("color: #807d72; font-size: 11.5px; background: transparent;")
        snd_text_vbox.addWidget(snd_title)
        snd_text_vbox.addWidget(snd_desc)
        row_snd.addLayout(snd_text_vbox, 1)

        self.sw_sound = CursorToggleSwitch(checked=self.config.get("sound_feedback", True), parent=self)
        self.sw_sound.toggled.connect(self._on_sound_sw_toggled)
        row_snd.addWidget(self.sw_sound)
        o_layout.addLayout(row_snd)

        layout.addWidget(card_opts)
        layout.addStretch()
        return w

    # ---------------- PAGE 2: Speech Models Hub ----------------
    def _build_models_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 6, 8, 6)
        layout.setSpacing(14)

        # Dropdown rapid switcher
        top_card = QFrame()
        top_card.setObjectName("card")
        tc_layout = QVBoxLayout(top_card)
        tc_layout.setSpacing(8)

        tc_layout.addWidget(self._make_header("ACTIVE SPEECH MODEL"))

        sel_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self._populate_models()
        self.model_combo.currentIndexChanged.connect(self._on_model_selection_changed)
        sel_row.addWidget(self.model_combo, 1)
        tc_layout.addLayout(sel_row)

        layout.addWidget(top_card)

        # Interactive Model Hub Catalog Cards
        layout.addWidget(self._make_header("OFFLINE MODEL CATALOG"))

        self.model_card_widgets = {}
        for key, info in MODEL_CATALOG.items():
            card = self._build_single_model_card(key, info)
            self.model_card_widgets[key] = card
            layout.addWidget(card)

        scroll.setWidget(w)
        return scroll

    def _build_single_model_card(self, key: str, info: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        # Header: Name + Pastel Category Badge
        header_row = QHBoxLayout()
        name_lbl = QLabel(info["name"], self)
        name_lbl.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        name_lbl.setStyleSheet("color: #26251e; background: transparent;")

        # AI-timeline pastel pill mapping
        badge_text = info.get("badge", "Offline")
        if "বাংলা" in badge_text or "bengali" in key:
            # Lavender token (Cursor Edit)
            bg, fg, border = "#f0e8f7", "#643ba0", "#c0a8dd"
        elif "हिन्दी" in badge_text or "hindi" in key:
            # Peach token (Cursor Thinking)
            bg, fg, border = "#fbf0eb", "#8c4524", "#dfa88f"
        elif ".en" in key:
            # Pastel Blue token (Cursor Read)
            bg, fg, border = "#edf3fa", "#22538b", "#9fbbe0"
        else:
            # Mint token (Cursor Grep)
            bg, fg, border = "#eff7f0", "#1f6d2b", "#9fc9a2"

        badge_lbl = QLabel(badge_text, self)
        badge_lbl.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        badge_lbl.setStyleSheet(f"""
            background-color: {bg};
            color: {fg};
            border: 1px solid {border};
            border-radius: 9999px;
            padding: 2px 8px;
        """)

        header_row.addWidget(name_lbl)
        header_row.addWidget(badge_lbl)
        header_row.addStretch()

        # Switch button or Active tag
        is_active = (self.config.get("model_size") == key)
        if is_active:
            status_tag = QLabel("● Active", self)
            status_tag.setFont(QFont("JetBrains Mono", 10, QFont.Weight.Bold))
            status_tag.setStyleSheet("color: #1f8a65; background: transparent;")
            header_row.addWidget(status_tag)
        else:
            switch_btn = QPushButton("Use Model")
            switch_btn.setFixedSize(96, 28)
            switch_btn.clicked.connect(lambda _, k=key: self._switch_to_model(k))
            header_row.addWidget(switch_btn)

        card_layout.addLayout(header_row)

        # Description
        desc_lbl = QLabel(info.get("description", ""), self)
        desc_lbl.setStyleSheet("color: #5a5852; font-size: 12px; background: transparent;")
        desc_lbl.setWordWrap(True)
        card_layout.addWidget(desc_lbl)

        # Specs Meta Footer in Monospace
        meta_row = QHBoxLayout()
        meta_row.setSpacing(14)

        speed_lbl = QLabel(f"⚡ {info.get('speed', '')}", self)
        speed_lbl.setStyleSheet("color: #807d72; font-size: 11px; font-family: 'JetBrains Mono', Consolas, monospace; background: transparent;")

        ram_lbl = QLabel(f"RAM: {info.get('ram', '')}", self)
        ram_lbl.setStyleSheet("color: #807d72; font-size: 11px; font-family: 'JetBrains Mono', Consolas, monospace; background: transparent;")

        size_lbl = QLabel(f"Disk: ~{info.get('size_mb', '')} MB", self)
        size_lbl.setStyleSheet("color: #807d72; font-size: 11px; font-family: 'JetBrains Mono', Consolas, monospace; background: transparent;")

        installed = is_model_installed(key)
        ready_lbl = QLabel("✓ Downloaded" if installed else "📥 Available", self)
        ready_lbl.setStyleSheet("color: #1f8a65; font-weight: 600; font-size: 11px; background: transparent;" if installed else "color: #c08532; font-size: 11px; background: transparent;")

        meta_row.addWidget(speed_lbl)
        meta_row.addWidget(ram_lbl)
        meta_row.addWidget(size_lbl)
        meta_row.addStretch()
        meta_row.addWidget(ready_lbl)

        card_layout.addLayout(meta_row)
        return card

    # ---------------- PAGE 3: Playground & Diagnostics ----------------
    def _build_playground_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        c_layout.addWidget(self._make_header("DICTATION SANDBOX"))

        hk = self.config.get("hotkey", "ctrl_r")
        hk_name = "Right Ctrl" if hk == "ctrl_r" else ("Left Ctrl" if hk == "ctrl_l" else hk.upper())
        dur = self.config.get("long_press_seconds", 1.0)

        self.test_box = QTextEdit()
        self.test_box.setPlaceholderText(f"Dictate text here using {hk_name} (or click 'Record 3-Second Test' below)...")
        self.test_box.setMinimumHeight(140)
        c_layout.addWidget(self.test_box)

        btn_row = QHBoxLayout()
        # Signature Cursor Orange button
        self.test_btn = QPushButton("Record 3-Second Test")
        self.test_btn.setObjectName("primaryBtn")
        self.test_btn.setMinimumHeight(38)
        self.test_btn.clicked.connect(self._on_test_record_clicked)
        btn_row.addWidget(self.test_btn, 1)

        clear_btn = QPushButton("Clear")
        clear_btn.setMinimumHeight(38)
        clear_btn.clicked.connect(lambda: self.test_box.clear())
        btn_row.addWidget(clear_btn)
        c_layout.addLayout(btn_row)

        self.diag_info = QLabel(f"Hold {hk_name} {dur:.1f}s anywhere in Windows to voice type directly into any app.", self)
        self.diag_info.setStyleSheet("color: #807d72; font-size: 11.5px; background: transparent;")
        c_layout.addWidget(self.diag_info)

        layout.addWidget(card)
        layout.addStretch()
        return w

    def _make_header(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setObjectName("sectionHeader")
        return lbl

    # ---------------- Handlers & Controllers ----------------

    def _populate_models(self):
        self.model_combo.clear()
        for key, info in MODEL_CATALOG.items():
            installed = is_model_installed(key)
            status_tag = "✓ Ready" if installed else "📥 Download"
            display_text = f"{info['name']} — {status_tag}"
            self.model_combo.addItem(display_text, key)

        current_m = self.config.get("model_size", "small")
        idx = self.model_combo.findData(current_m)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _populate_audio_devices(self):
        try:
            devices = sd.query_devices()
            default_in = sd.default.device[0]
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = f"{dev['name']}"
                    self.dev_combo.addItem(name, i)
                    if i == default_in:
                        self.dev_combo.setCurrentIndex(self.dev_combo.count() - 1)
        except Exception:
            self.dev_combo.addItem("Default Microphone", 0)

    def _init_mic_meter(self):
        self.meter_timer = QTimer(self)
        self.meter_timer.timeout.connect(self._poll_mic_level)
        self.meter_timer.start(40)

    def _poll_mic_level(self):
        if self.audio_recorder:
            try:
                vol = self.audio_recorder.get_latest_volume()
                self.vu_meter.set_level(vol * 2.2)
                if vol > 0.001:
                    db = 20 * math.log10(vol)
                    self.vu_db_label.setText(f"{db:.1f} dB")
                else:
                    self.vu_db_label.setText("-∞ dB")
            except Exception:
                pass

    def _on_device_changed(self, idx: int):
        dev_id = self.dev_combo.currentData()
        if dev_id is not None and self.audio_recorder:
            self.audio_recorder.set_device(dev_id)

    def _switch_to_model(self, key: str):
        idx = self.model_combo.findData(key)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _on_model_selection_changed(self):
        key = self.model_combo.currentData()
        if not key:
            return

        self.config["model_size"] = key
        self._save()

        if self.transcriber:
            success = self.transcriber.change_model(key)
            if success:
                self.model_switched.emit(key)
                self.status_pill.setText(f"● {key.upper()} (CPU int8)")
                self._refresh_model_page_cards()

    def _refresh_model_page_cards(self):
        active_key = self.config.get("model_size")
        for key, card in self.model_card_widgets.items():
            is_active = (key == active_key)
            card_layout = card.layout()
            if card_layout and card_layout.count() > 0:
                header_row = card_layout.itemAt(0).layout()
                if header_row and header_row.count() >= 3:
                    item = header_row.itemAt(header_row.count() - 1)
                    if item.widget():
                        w = item.widget()
                        if is_active and isinstance(w, QPushButton):
                            w.hide()
                        elif not is_active and isinstance(w, QLabel) and "Active" in w.text():
                            w.setText("Inactive")

    def _on_lang_changed(self):
        l = self.lang_combo.currentData()
        self.config["language"] = l
        self._save()

    def _on_slider_changed(self, val):
        secs = val / 10.0
        self.duration_val_lbl.setText(f"{secs:.1f}s")
        self.config["long_press_seconds"] = secs
        self._save()

    def _on_format_sw_toggled(self, checked: bool):
        self.config["auto_format"] = checked
        self._save()

    def _on_sound_sw_toggled(self, checked: bool):
        self.config["sound_feedback"] = checked
        self._save()

    def _save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.config_updated.emit(self.config)
        except Exception as e:
            print("Failed to save config:", e)

    def _on_test_record_clicked(self):
        self.test_btn.setEnabled(False)
        self.test_btn.setText("Listening... Speak now")
        self.test_box.setPlaceholderText("Recording 3 seconds...")
        QTimer.singleShot(100, self._do_test_recording)

    def _do_test_recording(self):
        def _worker():
            try:
                rec = sd.rec(int(3.0 * 16000), samplerate=16000, channels=1, dtype='float32')
                sd.wait()
                audio = rec.flatten()
                lang = self.config.get("language", "auto")
                prompt = self.config.get("initial_prompt", None)
                text, detected_lang = self.transcriber.transcribe(audio, language=lang, initial_prompt=prompt)
                if self.config.get("auto_format", True) and self.formatter:
                    text = self.formatter.format(text, language=detected_lang)

                QTimer.singleShot(0, lambda: self._show_test_result(text, detected_lang))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._show_test_result(f"Error: {e}", "err"))

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _show_test_result(self, text: str, lang: str):
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Record 3-Second Test")
        current = self.test_box.toPlainText()
        new_text = (current + " " + text).strip() if current else text
        self.test_box.setText(new_text)
