"""Hybrid Action Executor: UIA Input, Thread-Safe COM (Excel/MATLAB), and Guarded Shell."""

from __future__ import annotations

import subprocess
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from desktop_pilot.sandbox_guard import SandboxGuard


@dataclass
class ActionResult:
    success: bool
    output: str
    error: str = ""
    stderr_tail: str = ""


class HybridExecutor:
    def __init__(self, guard: SandboxGuard, dry_run: bool = False) -> None:
        self.guard = guard
        self.dry_run = dry_run

    def execute_step(self, action_type: str, payload: Dict[str, Any]) -> ActionResult:
        if self.dry_run:
            return ActionResult(
                success=True,
                output=f"[DRY-RUN] Previewed {action_type}: {payload}",
            )

        if action_type == "shell":
            return self._run_shell(payload.get("command", ""), cwd=payload.get("cwd"))
        if action_type == "com_python":
            return self._run_com_python(payload.get("code", ""))
        if action_type in ("uia_click", "uia_type"):
            return self._run_uia_action(action_type, payload)
        return ActionResult(False, "", error=f"Unsupported action_type: {action_type}")

    def _run_shell(self, command: str, cwd: Optional[str] = None) -> ActionResult:
        decision = self.guard.validate_shell_command(command)
        if not decision.allowed:
            return ActionResult(False, "", error=decision.reason)
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0:
                return ActionResult(True, proc.stdout.strip() or "Shell command completed.")
            return ActionResult(
                False,
                proc.stdout.strip(),
                error=f"Shell exited with code {proc.returncode}",
                stderr_tail=proc.stderr,
            )
        except Exception as exc:
            return ActionResult(False, "", error=str(exc), stderr_tail=traceback.format_exc())

    def _run_com_python(self, code: str) -> ActionResult:
        if not code.strip():
            return ActionResult(False, "", error="Empty COM/Python script payload.")

        local_ns: Dict[str, Any] = {"__name__": "__desktop_pilot_task__"}
        com_initialized = False
        try:
            if sys.platform == "win32":
                try:
                    import pythoncom  # type: ignore

                    pythoncom.CoInitialize()
                    com_initialized = True
                except ImportError:
                    pass
            exec(compile(code, "<fast_coder_com_script>", "exec"), local_ns, local_ns)
            result_summary = str(local_ns.get("RESULT", "COM/Python script executed successfully."))
            return ActionResult(True, result_summary)
        except Exception as exc:
            return ActionResult(
                False,
                "",
                error=f"{type(exc).__name__}: {exc}",
                stderr_tail=traceback.format_exc(),
            )
        finally:
            if com_initialized:
                try:
                    import pythoncom  # type: ignore

                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _run_uia_action(self, action_type: str, payload: Dict[str, Any]) -> ActionResult:
        x = int(payload.get("x", 0))
        y = int(payload.get("y", 0))
        text = str(payload.get("text", ""))
        if sys.platform != "win32":
            return ActionResult(
                True,
                f"[Simulated {action_type}] at ({x}, {y}) text={text!r}",
            )
        try:
            import ctypes

            user32 = ctypes.windll.user32
            user32.SetCursorPos(x, y)
            if action_type == "uia_click":
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
                return ActionResult(True, f"Clicked at ({x}, {y})")
            return ActionResult(True, f"Positioned at ({x}, {y}) for text input ({len(text)} chars)")
        except Exception as exc:
            return ActionResult(False, "", error=str(exc), stderr_tail=traceback.format_exc())
