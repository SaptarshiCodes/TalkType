"""
ui_pill.py - Luxury Apple/Raycast-grade Floating HUD for TalkType.
Features:
- Obsidian glassmorphism with dynamic specular edge lighting.
- Unified high-DPI state indicator (hold countdown ring, mic-reactive fluid soundwaves,
  cosmic transcription spinner, formatting sparkle, and crisp emerald checkmark).
- Smart auto-sizing capsule that adapts dynamically to text length and Windows DPI scaling.
- Focus-safe non-activating window flags (WS_EX_NOACTIVATE).
"""

import sys
import ctypes
import math
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject, QRectF, QRect
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QFontMetrics, QPainterPath

from talktype.ui.motion import SpringDamper

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008


class UnifiedIndicatorWidget(QWidget):
    """
    Seamless 32x32 indicator that handles all states without awkward show/hide layout jumps:
    - 'hold': High-precision circular countdown arc with glowing progress head.
    - 'recording': 5 fluid audio-reactive bars that spring with mic volume.
    - 'transcribing': Dual-arc cosmic aurora spinner.
    - 'formatting': Rotating amber diamond sparkle.
    - 'done': Crisp emerald checkmark badge.
    - 'no_speech': Muted neutral dot.
    - 'info': Purple crystal badge.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.state = "idle"  # idle, hold, recording, transcribing, formatting, done, no_speech, info
        self.progress = 0.0
        self.target_volume = 0.0
        self.current_heights = [4.0] * 5
        self.bar_springs = [SpringDamper(initial_value=4.0, stiffness=320.0, damping=24.0) for _ in range(5)]
        self.phase = 0.0

    def set_state(self, state: str):
        self.state = state
        self.update()

    def set_progress(self, p: float):
        self.progress = max(0.0, min(1.0, p))
        self.update()

    def set_volume(self, vol: float):
        self.target_volume = max(0.0, min(1.0, vol))

    def update_animation(self):
        self.phase += 0.12

        if self.state == "recording":
            # 5 symmetric audio bars driven by physical spring dampers
            weights = [0.55, 1.1, 1.6, 1.1, 0.55]
            for i in range(5):
                noise = math.sin(self.phase * 2.6 + i * 1.1) * 1.4
                target_h = 4.0 + (self.target_volume * 18.0 * weights[i]) + max(0.0, noise)
                target_h = min(22.0, max(4.0, target_h))
                self.bar_springs[i].set_target(target_h)
                self.current_heights[i] = self.bar_springs[i].step(0.025)
        elif self.state == "transcribing":
            pass  # Continuous rotation handled via self.phase in paintEvent
        elif self.state == "formatting":
            pass
        else:
            for i in range(5):
                self.bar_springs[i].set_target(4.0)
                self.current_heights[i] = self.bar_springs[i].step(0.025)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_x, mid_y = w / 2.0, h / 2.0

        if self.state == "hold":
            # 1. Circular countdown progress ring
            # Background track
            pen_track = QPen(QColor(255, 255, 255, 28), 2.5)
            painter.setPen(pen_track)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(3, 3, 26, 26, 0, 360 * 16)

            # Sweeping gradient arc
            if self.progress > 0:
                gradient = QLinearGradient(0, 0, 32, 32)
                gradient.setColorAt(0.0, QColor("#38bdf8"))  # Electric sky
                gradient.setColorAt(1.0, QColor("#a855f7"))  # Neon purple
                pen_arc = QPen(QBrush(gradient), 2.6)
                pen_arc.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen_arc)
                span_angle = int(self.progress * 360 * 16)
                painter.drawArc(3, 3, 26, 26, 90 * 16, -span_angle)

                # Glowing center beacon that intensifies as countdown finishes
                alpha = int(80 + self.progress * 175)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(56, 189, 248, alpha))
                painter.drawEllipse(int(mid_x - 3), int(mid_y - 3), 6, 6)

        elif self.state == "recording":
            # 2. 5 fluid audio-reactive soundwave bars
            bar_w = 3.0
            gap = 2.8
            total_bars_w = 5 * bar_w + 4 * gap
            start_x = (w - total_bars_w) / 2.0

            for i in range(5):
                bar_h = max(4.0, min(22.0, self.current_heights[i]))
                x = start_x + i * (bar_w + gap)
                y = mid_y - bar_h / 2.0

                grad = QLinearGradient(x, y, x, y + bar_h)
                grad.setColorAt(0.0, QColor("#fb7185"))  # Vibrant rose coral
                grad.setColorAt(1.0, QColor("#ef4444"))  # Vivid ruby red

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)

        elif self.state == "transcribing":
            # 3. Dual-arc cosmic aurora spinner
            # Outer subtle track
            painter.setPen(QPen(QColor(255, 255, 255, 20), 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(4, 4, 24, 24, 0, 360 * 16)

            # Arc 1: Sky Blue
            angle1 = int((self.phase * 50) % 360)
            pen1 = QPen(QColor("#38bdf8"), 2.4)
            pen1.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen1)
            painter.drawArc(4, 4, 24, 24, angle1 * 16, 120 * 16)

            # Arc 2: Indigo Purple (opposing)
            pen2 = QPen(QColor("#c084fc"), 2.4)
            pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen2)
            painter.drawArc(4, 4, 24, 24, (angle1 + 180) * 16, 100 * 16)

            # Center shimmer dot
            pulse = (math.sin(self.phase * 3.0) + 1.0) / 2.0
            dot_r = 2.0 + pulse * 1.5
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(192, 132, 252, int(150 + pulse * 105)))
            painter.drawEllipse(QRectF(mid_x - dot_r, mid_y - dot_r, dot_r * 2, dot_r * 2))

        elif self.state == "formatting":
            # 4. Rotating Amber Diamond / Sparkle
            painter.translate(mid_x, mid_y)
            painter.rotate((self.phase * 60) % 360)

            painter.setPen(Qt.PenStyle.NoPen)
            grad = QLinearGradient(-8, -8, 8, 8)
            grad.setColorAt(0.0, QColor("#fde047"))  # Radiant amber
            grad.setColorAt(1.0, QColor("#eab308"))  # Gold
            painter.setBrush(QBrush(grad))

            # 4-point sparkle polygon
            path = QPainterPath()
            path.moveTo(0, -9)
            path.quadTo(0, 0, 9, 0)
            path.quadTo(0, 0, 0, 9)
            path.quadTo(0, 0, -9, 0)
            path.quadTo(0, 0, 0, -9)
            painter.drawPath(path)
            painter.resetTransform()

        elif self.state == "done":
            # 5. Crisp Emerald Checkmark Badge
            painter.setPen(Qt.PenStyle.NoPen)
            grad = QLinearGradient(0, 4, 0, 28)
            grad.setColorAt(0.0, QColor("#22c55e"))
            grad.setColorAt(1.0, QColor("#16a34a"))
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(4, 4, 24, 24)

            # Pure white checkmark
            pen_chk = QPen(Qt.GlobalColor.white, 2.4)
            pen_chk.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen_chk.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen_chk)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            chk_path = QPainterPath()
            chk_path.moveTo(11, 16)
            chk_path.lineTo(15, 20)
            chk_path.lineTo(21, 12)
            painter.drawPath(chk_path)

        elif self.state == "no_speech":
            # Muted neutral circle with dash
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(113, 113, 122, 160))
            painter.drawEllipse(6, 6, 20, 20)

            painter.setPen(QPen(Qt.GlobalColor.white, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(12, 16, 20, 16)

        else:
            # Info / Sparkle badge
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(168, 85, 247, 200))
            painter.drawEllipse(5, 5, 22, 22)
            # Center diamond
            painter.setBrush(Qt.GlobalColor.white)
            path = QPainterPath()
            path.moveTo(mid_x, mid_y - 5)
            path.lineTo(mid_x + 5, mid_y)
            path.lineTo(mid_x, mid_y + 5)
            path.lineTo(mid_x - 5, mid_y)
            path.closeSubpath()
            painter.drawPath(path)


class StatusBadgeWidget(QWidget):
    """
    Subtle keyboard keycap / badge pill on the right side of the HUD.
    Never clips, dynamic auto-padding.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ""
        self.fg_color = QColor("#a1a1aa")
        self.bg_color = QColor(255, 255, 255, 14)
        self.border_color = QColor(255, 255, 255, 24)
        self.setFont(QFont("Segoe UI Semibold", 9))
        self.setFixedHeight(24)

    def set_badge(self, text: str, fg="#a1a1aa", bg="rgba(255, 255, 255, 14)", border="rgba(255, 255, 255, 24)"):
        self.text = text
        self.fg_color = QColor(fg)
        self.bg_color = QColor(bg) if isinstance(bg, str) and not bg.startswith("rgba") else (QColor(bg) if isinstance(bg, QColor) else QColor(255, 255, 255, 14))
        self.border_color = QColor(border) if isinstance(border, str) and not border.startswith("rgba") else (QColor(border) if isinstance(border, QColor) else QColor(255, 255, 255, 24))
        
        # Calculate dynamic width to guarantee no text clipping
        fm = QFontMetrics(self.font())
        text_w = fm.horizontalAdvance(self.text) if self.text else 0
        if self.text:
            self.setFixedWidth(text_w + 18)
            self.show()
        else:
            self.setFixedWidth(0)
            self.hide()
        self.update()

    def paintEvent(self, event):
        if not self.text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        r = rect.height() / 2.0

        painter.setPen(QPen(self.border_color, 1.0))
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRoundedRect(rect, r, r)

        painter.setPen(self.fg_color)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)


class FloatingPillHUD(QWidget):
    """
    Ultra-sleek, Apple/Raycast-grade floating pill capsule HUD for TalkType.
    Features obsidian glassmorphism, fluid audio responsiveness,
    smart auto-sizing capsule, and focus-safe Windows integration.
    """
    def __init__(self, audio_recorder=None, hotkey_name: str = "tab"):
        super().__init__()
        self.audio_recorder = audio_recorder
        self._hotkey_name = hotkey_name
        self.state = "idle"
        self.fade_animation = None
        self._init_window()
        self._init_ui()
        self._init_timer()

    @property
    def hotkey_display(self) -> str:
        hk = getattr(self, "_hotkey_name", "ctrl_r")
        hk_map = {
            "ctrl_l": "Left Ctrl", "ctrl_r": "Right Ctrl", "ctrl": "Ctrl",
            "tab": "Tab",
            "alt_l": "Alt", "alt_r": "Alt", "alt": "Alt",
            "shift_l": "Shift", "shift_r": "Shift",
            "caps_lock": "Caps Lock"
        }
        return hk_map.get(hk.lower(), hk.upper())

    def set_hotkey_name(self, name: str):
        self._hotkey_name = name

    def _init_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedHeight(50)
        self.setMinimumWidth(360)

    def _apply_no_activate(self):
        """Ensures Windows OS never steals typing focus from the active document/app."""
        try:
            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            )
        except Exception:
            pass

    def _center_near_bottom(self):
        screen = self.screen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - 110
        self.move(x, y)

    def _init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(16, 6, 16, 6)
        self.main_layout.setSpacing(12)

        # 1. Left unified indicator
        self.indicator = UnifiedIndicatorWidget(self)
        self.main_layout.addWidget(self.indicator)

        # 2. Middle status label
        self.label = QLabel("TalkType Ready", self)
        # Segoe UI Variable Display or Segoe UI Semibold
        font = QFont("Segoe UI Variable Display", 10)
        font.setWeight(QFont.Weight.DemiBold)
        self.label.setFont(font)
        self.label.setStyleSheet("color: #f4f4f5; background: transparent;")
        self.label.setWordWrap(False)
        self.main_layout.addWidget(self.label, 1)

        # 3. Right secondary badge
        self.badge = StatusBadgeWidget(self)
        self.main_layout.addWidget(self.badge)

        # Diffused ambient drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

    def _init_timer(self):
        # 40 FPS high-precision animation loop
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self.anim_timer.start(25)

    def _on_anim_tick(self):
        if self.state == "recording" and self.audio_recorder:
            try:
                vol = self.audio_recorder.get_latest_volume()
                boosted = min(1.0, math.sqrt(vol) * 1.6)
                self.indicator.set_volume(boosted)
            except Exception:
                pass
        self.indicator.update_animation()

    def _adapt_capsule_size(self):
        """Dynamically and smoothly animates capsule width with OutCubic motion so text is never clipped."""
        fm = QFontMetrics(self.label.font())
        label_w = fm.horizontalAdvance(self.label.text())
        badge_w = self.badge.width() if self.badge.isVisible() else 0

        target_w = 32 + 32 + 12 + label_w + 12 + badge_w + 24
        target_w = max(360, min(560, target_w))

        screen = self.screen().geometry()
        target_x = (screen.width() - target_w) // 2
        target_y = screen.height() - 110
        target_rect = QRect(target_x, target_y, target_w, self.height())

        if self.isVisible():
            if not hasattr(self, "_geo_anim") or self._geo_anim is None:
                self._geo_anim = QPropertyAnimation(self, b"geometry", self)
                self._geo_anim.setDuration(160)
                self._geo_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._geo_anim.stop()
            self._geo_anim.setStartValue(self.geometry())
            self._geo_anim.setEndValue(target_rect)
            self._geo_anim.start()
        else:
            self.setGeometry(target_rect)

    def paintEvent(self, event):
        """Draws obsidian glassmorphic capsule with specular edge lighting."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        radius = rect.height() / 2.0

        # Base obsidian glass gradient
        bg_gradient = QLinearGradient(0, 0, 0, self.height())
        bg_gradient.setColorAt(0.0, QColor(18, 20, 27, 248))
        bg_gradient.setColorAt(1.0, QColor(10, 11, 15, 252))
        painter.setBrush(QBrush(bg_gradient))

        # Dynamic specular edge lighting
        border_gradient = QLinearGradient(0, 0, 0, self.height())
        if self.state == "recording":
            border_gradient.setColorAt(0.0, QColor("#fb7185"))
            border_gradient.setColorAt(1.0, QColor(239, 68, 68, 80))
            border_pen = QPen(QBrush(border_gradient), 1.3)
        elif self.state == "transcribing":
            border_gradient.setColorAt(0.0, QColor("#38bdf8"))
            border_gradient.setColorAt(1.0, QColor(168, 85, 247, 80))
            border_pen = QPen(QBrush(border_gradient), 1.3)
        elif self.state == "formatting":
            border_gradient.setColorAt(0.0, QColor("#fde047"))
            border_gradient.setColorAt(1.0, QColor(234, 179, 8, 80))
            border_pen = QPen(QBrush(border_gradient), 1.3)
        elif self.state == "done":
            border_gradient.setColorAt(0.0, QColor("#4ade80"))
            border_gradient.setColorAt(1.0, QColor(34, 197, 94, 80))
            border_pen = QPen(QBrush(border_gradient), 1.3)
        elif self.state == "hold":
            border_gradient.setColorAt(0.0, QColor(56, 189, 248, 180))
            border_gradient.setColorAt(1.0, QColor(168, 85, 247, 60))
            border_pen = QPen(QBrush(border_gradient), 1.2)
        else:
            border_gradient.setColorAt(0.0, QColor(255, 255, 255, 45))
            border_gradient.setColorAt(1.0, QColor(255, 255, 255, 12))
            border_pen = QPen(QBrush(border_gradient), 1.0)

        painter.setPen(border_pen)
        painter.drawRoundedRect(QRectF(rect), radius, radius)

        # Subtle specular top highlight curve
        inner_top = QRectF(rect.x() + 10, rect.y() + 1, rect.width() - 20, 1.0)
        painter.setPen(QColor(255, 255, 255, 25))
        painter.drawLine(int(inner_top.left()), int(inner_top.top()), int(inner_top.right()), int(inner_top.top()))

    # ---- State Controllers ----

    def show_hold_progress(self, action: str, elapsed: float, target: float):
        self.state = "hold"
        self._ensure_visible()
        self.indicator.set_state("hold")
        pct = min(1.0, elapsed / max(target, 0.1))
        self.indicator.set_progress(pct)

        self.label.setText(f"Hold {self.hotkey_display} to {action}")
        self.label.setStyleSheet("color: #fef08a; font-weight: 600; font-size: 13px;")

        # Keycap style badge
        self.badge.set_badge(
            f"{elapsed:.1f}s / {target:.1f}s",
            fg="#fef08a",
            bg=QColor(254, 240, 138, 22),
            border=QColor(254, 240, 138, 50)
        )
        self._adapt_capsule_size()
        self.update()

    def show_recording(self):
        self.state = "recording"
        self._ensure_visible()
        self.indicator.set_state("recording")

        self.label.setText("Listening...")
        self.label.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 13px;")

        # Keyboard prompt badge
        self.badge.set_badge(
            f"Tap {self.hotkey_display} to stop",
            fg="#fca5a5",
            bg=QColor(239, 68, 68, 22),
            border=QColor(239, 68, 68, 50)
        )
        self._adapt_capsule_size()
        self.update()

    def show_transcribing(self, model_name: str = "Whisper"):
        self.state = "transcribing"
        self._ensure_visible()
        self.indicator.set_state("transcribing")

        self.label.setText("Transcribing speech...")
        self.label.setStyleSheet("color: #bae6fd; font-weight: 600; font-size: 13px;")

        self.badge.set_badge(
            f"⚡ {model_name}",
            fg="#38bdf8",
            bg=QColor(56, 189, 248, 20),
            border=QColor(56, 189, 248, 50)
        )
        self._adapt_capsule_size()
        self.update()

    def show_formatting(self):
        self.state = "formatting"
        self._ensure_visible()
        self.indicator.set_state("formatting")

        self.label.setText("Formatting & Polishing...")
        self.label.setStyleSheet("color: #fde047; font-weight: 600; font-size: 13px;")

        self.badge.set_badge(
            "✦ Auto-Format",
            fg="#fde047",
            bg=QColor(250, 204, 21, 20),
            border=QColor(250, 204, 21, 50)
        )
        self._adapt_capsule_size()
        self.update()

    def show_done(self):
        self.state = "done"
        self._ensure_visible()
        self.indicator.set_state("done")

        self.label.setText("Formatted & Pasted")
        self.label.setStyleSheet("color: #86efac; font-weight: 600; font-size: 13px;")

        self.badge.set_badge(
            "Done ✓",
            fg="#4ade80",
            bg=QColor(34, 197, 94, 25),
            border=QColor(74, 222, 128, 60)
        )
        self._adapt_capsule_size()
        self.update()
        QTimer.singleShot(850, self.smooth_hide)

    def show_no_speech(self):
        self.state = "no_speech"
        self._ensure_visible()
        self.indicator.set_state("no_speech")

        self.label.setText("No Speech Detected")
        self.label.setStyleSheet("color: #a1a1aa; font-weight: 500; font-size: 13px;")

        self.badge.set_badge(
            "Try Again",
            fg="#a1a1aa",
            bg=QColor(255, 255, 255, 12),
            border=QColor(255, 255, 255, 25)
        )
        self._adapt_capsule_size()
        self.update()
        QTimer.singleShot(1100, self.smooth_hide)

    def show_model_switched(self, model_name: str):
        self.state = "info"
        self._ensure_visible()
        self.indicator.set_state("info")

        self.label.setText(f"Active Model: {model_name}")
        self.label.setStyleSheet("color: #c084fc; font-weight: 600; font-size: 13px;")

        self.badge.set_badge(
            "Ready",
            fg="#c084fc",
            bg=QColor(192, 132, 252, 22),
            border=QColor(192, 132, 252, 50)
        )
        self._adapt_capsule_size()
        self.update()
        QTimer.singleShot(1400, self.smooth_hide)

    def _ensure_visible(self):
        if not self.isVisible():
            self._apply_no_activate()
            self.setWindowOpacity(0.0)
            self.show()
            self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
            self.fade_animation.setDuration(160)
            self.fade_animation.setStartValue(0.0)
            self.fade_animation.setEndValue(1.0)
            self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.fade_animation.start()

    def smooth_hide(self):
        if self.isVisible() and self.state in ("done", "info", "no_speech"):
            self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
            self.fade_animation.setDuration(220)
            self.fade_animation.setStartValue(self.windowOpacity())
            self.fade_animation.setEndValue(0.0)
            self.fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)
            self.fade_animation.finished.connect(self._finish_hide)
            self.fade_animation.start()

    def immediate_hide(self):
        self.state = "idle"
        self.hide()

    def _finish_hide(self):
        self.state = "idle"
        self.hide()
