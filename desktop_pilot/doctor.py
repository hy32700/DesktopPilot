"""Preflight Environment & Configuration Doctor (Pain Point #6)."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from desktop_pilot.grounding_som import enable_per_monitor_dpi_awareness
from desktop_pilot.llm_router import LLMRouter


def run_preflight_checks(config_path: str = "config.json") -> Tuple[bool, List[str]]:
    lines: List[str] = []
    all_ok = True

    lines.append(f"[OK] Python {sys.version.split()[0]} on {platform.system()} ({platform.machine()})")
    dpi_status = enable_per_monitor_dpi_awareness()
    lines.append(f"[OK] DPI Awareness Mode: {dpi_status}")

    if sys.platform == "win32":
        try:
            import win32com.client  # type: ignore  # noqa: F401

            lines.append("[OK] pywin32 COM bridge available (Excel/MATLAB automation ready)")
        except ImportError:
            lines.append("[WARN] pywin32 not installed -> COM tasks will degrade to UIA/Shell fallback")
    else:
        lines.append("[INFO] Non-Windows OS detected -> Dry-Run, Skill Replay & Simulation modes active")

    cfg_file = Path(config_path)
    if not cfg_file.exists():
        lines.append(f"[WARN] '{config_path}' not found -> Run `python setup_wizard.py` or copy `config.example.json`")
        return False, lines

    try:
        cfg: Dict[str, Any] = json.loads(cfg_file.read_text(encoding="utf-8"))
        router = LLMRouter(cfg)
        if router.planner.is_configured:
            lines.append(f"[OK] Planner Endpoint: {router.planner.model} @ {router.planner.base_url}")
        else:
            lines.append("[FAIL] Planner API key missing in config.json")
            all_ok = False

        if router.single_endpoint_active:
            lines.append("[OK] Fast Coder Endpoint: Single-Endpoint Fallback Active (reusing Planner)")
        elif router.fast_coder.is_configured:
            lines.append(f"[OK] Fast Coder Endpoint: {router.fast_coder.model} @ {router.fast_coder.base_url}")
        else:
            lines.append("[FAIL] Fast Coder API key missing in config.json")
            all_ok = False
    except Exception as exc:
        lines.append(f"[FAIL] Invalid config.json: {exc}")
        all_ok = False

    return all_ok, lines
