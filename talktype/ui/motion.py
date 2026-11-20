"""
talktype/ui/motion.py - Modern Motion & Physics Animation Engine for TalkType.
Provides physics-based spring dampening, smooth animated stacked widget transitions,
and fluid easing curves following modern motion design principles.
"""

import math
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, pyqtProperty
from PyQt6.QtWidgets import QStackedWidget, QWidget, QGraphicsOpacityEffect


class SpringDamper:
    """
    Second-order harmonic spring-damper simulator for natural physical animations.
    Uses continuous physics integration: force = -stiffness * (x - target) - damping * v.
    """
    def __init__(self, initial_value: float = 0.0, stiffness: float = 240.0, damping: float = 22.0, mass: float = 1.0):
        self.value = initial_value
        self.target = initial_value
        self.velocity = 0.0
        self.stiffness = stiffness
        self.damping = damping
        self.mass = mass

    def set_target(self, target: float):
        self.target = target

    def snap_to(self, value: float):
        self.value = value
        self.target = value
        self.velocity = 0.0

    def step(self, dt: float = 0.016) -> float:
        """Steps physics simulation forward by dt seconds."""
        displacement = self.value - self.target
        spring_force = -self.stiffness * displacement
        damping_force = -self.damping * self.velocity
        acceleration = (spring_force + damping_force) / max(self.mass, 0.001)

        self.velocity += acceleration * dt
        self.value += self.velocity * dt

        # Sleep threshold when near equilibrium
        if abs(self.velocity) < 0.001 and abs(displacement) < 0.001:
            self.value = self.target
            self.velocity = 0.0

        return self.value


class AnimatedStackedWidget(QStackedWidget):
    """
    World-class animated stack transition engine.
    Replaces instantaneous page jumps with smooth, fluid horizontal slide & crossfade
    transitions using OutCubic easing curves.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._animating = False
        self._duration = 240
        self._easing = QEasingCurve.Type.OutCubic

    def slide_to_index(self, next_idx: int):
        """Animates transition to the widget at next_idx."""
        if self._animating or next_idx == self.currentIndex():
            return
        if next_idx < 0 or next_idx >= self.count():
            return

        current_idx = self.currentIndex()
        going_forward = next_idx > current_idx

        curr_widget = self.widget(current_idx)
        next_widget = self.widget(next_idx)

        w = self.width()
        h = self.height()

        next_x = w if going_forward else -w
        next_widget.setGeometry(next_x, 0, w, h)
        next_widget.show()
        next_widget.raise_()

        self._animating = True

        # Animating current widget out
        self.anim_curr = QPropertyAnimation(curr_widget, b"pos", self)
        self.anim_curr.setDuration(self._duration)
        self.anim_curr.setEasingCurve(self._easing)
        self.anim_curr.setStartValue(QPoint(0, 0))
        self.anim_curr.setEndValue(QPoint(-next_x, 0))

        # Animating next widget in
        self.anim_next = QPropertyAnimation(next_widget, b"pos", self)
        self.anim_next.setDuration(self._duration)
        self.anim_next.setEasingCurve(self._easing)
        self.anim_next.setStartValue(QPoint(next_x, 0))
        self.anim_next.setEndValue(QPoint(0, 0))

        def _on_finish():
            curr_widget.hide()
            curr_widget.move(0, 0)
            self.setCurrentIndex(next_idx)
            self._animating = False

        self.anim_next.finished.connect(_on_finish)
        self.anim_curr.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self.anim_next.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class PulseGenerator:
    """
    Generates sinusoidal and exponential harmonic breathing curves
    for micro-interactions (e.g. recording beacons, transcribing shimmer).
    """
    def __init__(self, frequency: float = 1.0):
        self.phase = 0.0
        self.frequency = frequency

    def update(self, dt: float = 0.025) -> float:
        self.phase += self.frequency * dt * 2.0 * math.pi
        # Normalized between 0.0 and 1.0
        return (math.sin(self.phase) + 1.0) / 2.0
