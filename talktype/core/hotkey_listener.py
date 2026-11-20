import time
import threading
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

KEY_MAPPING = {
    "ctrl_l": Key.ctrl_l,
    "ctrl_r": Key.ctrl_r,
    "ctrl": Key.ctrl_l,
    "tab": Key.tab,
    "alt_l": Key.alt_l,
    "alt_r": Key.alt_r,
    "alt": Key.alt_l,
    "shift_l": Key.shift_l,
    "shift_r": Key.shift_r,
    "caps_lock": Key.caps_lock,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
    "scroll_lock": Key.scroll_lock,
    "pause": Key.pause,
    "insert": Key.insert,
}

class HotkeyListener:
    def __init__(
        self,
        hotkey_name: str = "ctrl_l",
        trigger_mode: str = "long_press_toggle",
        long_press_seconds: float = 1.5,
        on_start_recording: Optional[Callable[[], None]] = None,
        on_stop_recording: Optional[Callable[[], None]] = None,
        on_hold_progress: Optional[Callable[[str, float, float], None]] = None,
        on_cancel_hold: Optional[Callable[[], None]] = None,
        # Push to talk fallbacks
        on_press_ptt: Optional[Callable[[], None]] = None,
        on_release_ptt: Optional[Callable[[float], None]] = None
    ):
        self.hotkey_name = hotkey_name.lower().strip()
        self.target_key = self._resolve_key(self.hotkey_name)
        self.trigger_mode = trigger_mode
        self.long_press_seconds = float(long_press_seconds)

        self.on_start_recording = on_start_recording
        self.on_stop_recording = on_stop_recording
        self.on_hold_progress = on_hold_progress
        self.on_cancel_hold = on_cancel_hold
        self.on_press_ptt = on_press_ptt
        self.on_release_ptt = on_release_ptt

        self.is_held = False
        self.press_time = 0.0
        self.listener = None
        self.enabled = True
        self.is_recording = False
        self._action_triggered = False

        self._timer_thread = None
        self._stop_timer = threading.Event()

    def _resolve_key(self, name: str):
        if name in KEY_MAPPING:
            return KEY_MAPPING[name]
        try:
            return KeyCode.from_char(name)
        except Exception:
            logger.warning(f"Unrecognized key '{name}', falling back to 'ctrl_l'")
            return Key.ctrl_l

    def set_hotkey(self, hotkey_name: str):
        self.hotkey_name = hotkey_name.lower().strip()
        self.target_key = self._resolve_key(self.hotkey_name)
        logger.info(f"Target hotkey updated to: {self.hotkey_name}")

    def set_recording(self, state: bool):
        """Synchronizes recording state from the application controller."""
        self.is_recording = state
        logger.debug(f"HotkeyListener recording state updated: {state}")

    def is_physically_held(self) -> bool:
        """Returns True if the physical key is currently depressed."""
        return self.is_held

    def _match_key(self, key):
        if self.target_key is None or key is None:
            return False
        if key == self.target_key:
            return True
        # Handle left/right/generic modifier equivalence
        if self.target_key in (Key.ctrl, Key.ctrl_l) and key in (Key.ctrl, Key.ctrl_l):
            return True
        if self.target_key in (Key.ctrl, Key.ctrl_r) and key in (Key.ctrl, Key.ctrl_r):
            return True
        if self.target_key in (Key.alt, Key.alt_l) and key in (Key.alt, Key.alt_l):
            return True
        if self.target_key in (Key.alt, Key.alt_r) and key in (Key.alt, Key.alt_r):
            return True
        if self.target_key in (Key.shift, Key.shift_l) and key in (Key.shift, Key.shift_l):
            return True
        if self.target_key in (Key.shift, Key.shift_r) and key in (Key.shift, Key.shift_r):
            return True
        return False

    def _hold_monitor_loop(self):
        """Monitors key hold duration to start recording."""
        while not self._stop_timer.is_set():
            now = time.time()
            elapsed = now - self.press_time

            # Only show visual progress ring after 0.2s to not flicker on fast Ctrl taps (like Ctrl+C)
            if elapsed >= 0.2 and not self._action_triggered:
                if self.on_hold_progress:
                    self.on_hold_progress("Start", elapsed, self.long_press_seconds)

            if elapsed >= self.long_press_seconds and not self._action_triggered:
                self._action_triggered = True
                self.is_recording = True
                logger.info(f"Long press reached ({self.long_press_seconds:.1f}s): Starting recording...")
                if self.on_start_recording:
                    self.on_start_recording()
                break

            time.sleep(0.04)

    def _on_press_event(self, key):
        if not self.enabled:
            return

        if self._match_key(key):
            if not self.is_held:
                self.is_held = True
                self.press_time = time.time()
                self._action_triggered = False

                if self.trigger_mode == "long_press_toggle":
                    if self.is_recording:
                        # RECORDING IS ACTIVE: Stop immediately on ANY click or press!
                        # No need to hold for another 1.5s - instant response when done speaking!
                        logger.info("Hotkey pressed while recording: STOPPING recording immediately!")
                        self._action_triggered = True
                        self.is_recording = False
                        self._stop_timer.set()
                        if self.on_stop_recording:
                            self.on_stop_recording()
                    else:
                        # IDLE: Require holding for long_press_seconds to start recording
                        self._stop_timer.clear()
                        self._timer_thread = threading.Thread(target=self._hold_monitor_loop, daemon=True)
                        self._timer_thread.start()
                else:
                    # Push-to-talk mode
                    if self.on_press_ptt:
                        self.on_press_ptt()

    def _on_release_event(self, key):
        if not self.enabled:
            return

        if self._match_key(key):
            duration = time.time() - self.press_time
            self.is_held = False
            self._stop_timer.set()

            if self.trigger_mode == "long_press_toggle":
                if not self._action_triggered:
                    # User released before hold completed while idle (e.g. quick Ctrl+C / Ctrl+V)
                    if self.on_cancel_hold:
                        self.on_cancel_hold()
                # If _action_triggered is True:
                # - If starting: hold monitor loop already triggered on_start_recording
                # - If stopping: _on_press_event already triggered on_stop_recording
            else:
                # Push-to-talk mode
                if self.on_release_ptt:
                    self.on_release_ptt(duration)

    def start(self):
        if self.listener is None:
            self.listener = keyboard.Listener(
                on_press=self._on_press_event,
                on_release=self._on_release_event
            )
            self.listener.daemon = True
            self.listener.start()
            logger.info(f"Hotkey listener started ({self.trigger_mode}, key='{self.hotkey_name}', duration={self.long_press_seconds}s).")

    def stop(self):
        self._stop_timer.set()
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
