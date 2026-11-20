import threading
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional


class RuntimePhase(Enum):
    IDLE = "idle"
    HOLDING = "holding"
    STARTING_RECORDING = "starting_recording"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    FORMATTING = "formatting"
    SWITCHING_MODEL = "switching_model"


@dataclass(frozen=True)
class RuntimeSnapshot:
    phase: RuntimePhase
    paused: bool
    active_model: str
    pending_model: Optional[str] = None
    stop_requested: bool = False

    @property
    def is_processing(self) -> bool:
        return self.phase in (RuntimePhase.TRANSCRIBING, RuntimePhase.FORMATTING)


class RuntimeStateStore:
    def __init__(self, active_model: str):
        self._lock = threading.RLock()
        self._state = RuntimeSnapshot(
            phase=RuntimePhase.IDLE,
            paused=False,
            active_model=active_model,
        )

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            return self._state

    def set_paused(self, paused: bool) -> RuntimeSnapshot:
        with self._lock:
            self._state = replace(self._state, paused=paused)
            return self._state

    def begin_hold(self) -> bool:
        with self._lock:
            if self._state.paused or self._state.phase not in (
                RuntimePhase.IDLE,
                RuntimePhase.HOLDING,
            ):
                return False
            if self._state.phase == RuntimePhase.IDLE:
                self._state = replace(self._state, phase=RuntimePhase.HOLDING)
            return True

    def cancel_hold(self) -> bool:
        with self._lock:
            if self._state.phase != RuntimePhase.HOLDING:
                return False
            self._state = replace(self._state, phase=RuntimePhase.IDLE)
            return True

    def begin_recording(self) -> bool:
        with self._lock:
            if self._state.paused or self._state.phase not in (
                RuntimePhase.IDLE,
                RuntimePhase.HOLDING,
            ):
                return False
            self._state = replace(
                self._state,
                phase=RuntimePhase.STARTING_RECORDING,
                stop_requested=False,
            )
            return True

    def finish_recording_start(self) -> bool:
        with self._lock:
            if self._state.phase != RuntimePhase.STARTING_RECORDING:
                return False
            stop_requested = self._state.stop_requested or self._state.paused
            self._state = replace(
                self._state,
                phase=RuntimePhase.RECORDING,
                stop_requested=False,
            )
            return stop_requested

    def abort_recording_start(self) -> bool:
        with self._lock:
            if self._state.phase != RuntimePhase.STARTING_RECORDING:
                return False
            self._state = replace(
                self._state,
                phase=RuntimePhase.IDLE,
                stop_requested=False,
            )
            return True

    def request_stop_recording(self) -> bool:
        with self._lock:
            if self._state.phase == RuntimePhase.STARTING_RECORDING:
                self._state = replace(self._state, stop_requested=True)
                return False
            if self._state.phase != RuntimePhase.RECORDING:
                return False
            self._state = replace(self._state, phase=RuntimePhase.TRANSCRIBING)
            return True

    def begin_formatting(self) -> bool:
        with self._lock:
            if self._state.phase != RuntimePhase.TRANSCRIBING:
                return False
            self._state = replace(self._state, phase=RuntimePhase.FORMATTING)
            return True

    def finish_processing(self) -> bool:
        with self._lock:
            if not self._state.is_processing:
                return False
            self._state = replace(self._state, phase=RuntimePhase.IDLE)
            return True

    def begin_model_switch(self, model_size: str) -> bool:
        with self._lock:
            if self._state.phase != RuntimePhase.IDLE:
                return False
            self._state = replace(
                self._state,
                phase=RuntimePhase.SWITCHING_MODEL,
                pending_model=model_size,
            )
            return True

    def finish_model_switch(self, model_size: str, success: bool) -> bool:
        with self._lock:
            if (
                self._state.phase != RuntimePhase.SWITCHING_MODEL
                or self._state.pending_model != model_size
            ):
                return False
            self._state = replace(
                self._state,
                phase=RuntimePhase.IDLE,
                active_model=model_size if success else self._state.active_model,
                pending_model=None,
            )
            return True
