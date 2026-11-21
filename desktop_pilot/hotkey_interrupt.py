"""Global Hotkey Pause/Resume Controller (Pain Point #1)."""

from __future__ import annotations

import sys
import threading
import time
from enum import Enum
from typing import Callable, Optional


class ExecutionState(str, Enum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESUMING_RECAPTURE = "RESUMING_RECAPTURE"
    STOPPED = "STOPPED"


class HotkeyInterruptController:
    """Monitors a global hotkey (default Ctrl+Alt+Space) to pause/resume agent execution."""

    VK_CONTROL = 0x11
    VK_MENU = 0x12
    VK_SPACE = 0x20

    def __init__(
        self,
        hotkey_label: str = "Ctrl+Alt+Space",
        on_state_change: Optional[Callable[[ExecutionState], None]] = None,
        poll_interval: float = 0.08,
    ) -> None:
        self.hotkey_label = hotkey_label
        self.on_state_change = on_state_change
        self.poll_interval = poll_interval
        self._state = ExecutionState.RUNNING
        self._lock = threading.Lock()
        self._resume_event = threading.Event()
        self._resume_event.set()
        self._stop_monitor = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def state(self) -> ExecutionState:
        with self._lock:
            return self._state

    def start(self) -> None:
        if sys.platform != "win32":
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_monitor.clear()
        self._thread = threading.Thread(
            target=self._win32_poll_loop,
            name="DesktopPilot-HotkeyMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_monitor.set()
        with self._lock:
            self._state = ExecutionState.STOPPED
            self._resume_event.set()

    def toggle_pause(self) -> ExecutionState:
        with self._lock:
            if self._state == ExecutionState.STOPPED:
                return self._state
            if self._state in (ExecutionState.RUNNING, ExecutionState.RESUMING_RECAPTURE):
                self._state = ExecutionState.PAUSED
                self._resume_event.clear()
            else:
                self._state = ExecutionState.RESUMING_RECAPTURE
                self._resume_event.set()
            new_state = self._state

        if self.on_state_change:
            self.on_state_change(new_state)
        return new_state

    def wait_if_paused(self) -> bool:
        self._resume_event.wait()
        with self._lock:
            if self._state == ExecutionState.RESUMING_RECAPTURE:
                self._state = ExecutionState.RUNNING
                return True
            return False

    def _win32_poll_loop(self) -> None:
        import ctypes

        user32 = ctypes.windll.user32
        was_pressed = False
        while not self._stop_monitor.is_set():
            ctrl = (user32.GetAsyncKeyState(self.VK_CONTROL) & 0x8000) != 0
            alt = (user32.GetAsyncKeyState(self.VK_MENU) & 0x8000) != 0
            space = (user32.GetAsyncKeyState(self.VK_SPACE) & 0x8000) != 0
            pressed = ctrl and alt and space
            if pressed and not was_pressed:
                self.toggle_pause()
            was_pressed = pressed
            time.sleep(self.poll_interval)
