"""Dual-Node Diagnostic Context Bridge & COM HRESULT Decoder (Pain Point #2)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


COM_HRESULT_CATALOG: Dict[str, str] = {
    "0x800A03EC": "Excel COM General/Range Error (check sheet name, 1-based cell index, or protected/modal dialog state).",
    "0x800401E3": "MK_E_UNAVAILABLE (COM object not running or not registered in Running Object Table).",
    "0x80010001": "RPC_E_CALL_REJECTED (Host application busy, e.g., Excel cell in edit mode or modal popup open).",
    "0x8001010A": "RPC_E_SERVERCALL_RETRYLATER (Server busy; retry after short backoff).",
    "0x80070005": "E_ACCESSDENIED (Permission denied or file locked by another process).",
    "0x80070002": "ERROR_FILE_NOT_FOUND (Target file or COM template path does not exist).",
    "0x80040154": "REGDB_E_CLASSNOTREG (COM class/application is not installed on this machine).",
}


def decode_hresult(error_text: str) -> Optional[str]:
    matches = re.findall(r"0x[0-9a-fA-F]{8}", error_text or "")
    for raw_code in matches:
        normalized = "0x" + raw_code[2:].upper()
        if normalized in COM_HRESULT_CATALOG:
            return f"{normalized}: {COM_HRESULT_CATALOG[normalized]}"
    if "-2146827284" in (error_text or ""):
        return f"0x800A03EC: {COM_HRESULT_CATALOG['0x800A03EC']}"
    if "-2147418111" in (error_text or ""):
        return f"0x80010001: {COM_HRESULT_CATALOG['0x80010001']}"
    return None


@dataclass
class ExecutionDiagnostic:
    step_index: int
    planner_intent: str
    action_type: str
    generated_payload: str
    error_message: str
    stderr_tail: str = ""
    active_window: str = ""
    attempt: int = 1
    hresult_hint: Optional[str] = field(init=False)

    def __post_init__(self) -> None:
        combined = f"{self.error_message}\n{self.stderr_tail}"
        self.hresult_hint = decode_hresult(combined)

    def to_coder_prompt_context(self) -> str:
        lines = [
            f"[Step {self.step_index} | Attempt {self.attempt}]",
            f"Planner Global Sub-Goal: {self.planner_intent}",
            f"Action Type: {self.action_type}",
            f"Active Window: {self.active_window or 'Unknown'}",
            f"Failed Payload:\n{self.generated_payload}",
            f"Error Message: {self.error_message}",
        ]
        if self.hresult_hint:
            lines.append(f"Decoded COM/Win32 Hint: {self.hresult_hint}")
        if self.stderr_tail:
            lines.append(f"Traceback / Stderr Tail:\n{self.stderr_tail[-1200:]}")
        return "\n".join(lines)

    def to_planner_escalation_digest(self) -> str:
        hint = f" ({self.hresult_hint})" if self.hresult_hint else ""
        return (
            f"ESCALATION at Step {self.step_index}: Fast Coder failed {self.attempt}x "
            f"on '{self.planner_intent}' via {self.action_type}. "
            f"Root error: {self.error_message}{hint}. "
            f"Please choose an alternative strategy (e.g., UIA/Grid fallback or file-level edit)."
        )


class DiagnosticHistory:
    def __init__(self, max_coder_retries: int = 2) -> None:
        self.max_coder_retries = max_coder_retries
        self.records: List[ExecutionDiagnostic] = []

    def record(self, diag: ExecutionDiagnostic) -> bool:
        self.records.append(diag)
        return diag.attempt > self.max_coder_retries
