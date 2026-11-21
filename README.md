# DesktopPilot v3.0

**Autonomous, Safe, and Self-Distilling Windows Desktop Agent**  
Hybrid Execution Engine: **Per-Monitor DPI UIA Set-of-Mark + Grid Vision** | **Thread-Safe COM (Excel / MATLAB)** | **Guarded Shell** | **Deterministic Skill Replay**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://www.python.org/)
[![Platform: Windows 10/11](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6.svg)](#)

---

## Why DesktopPilot v3.0?

1. **Instant Human-in-the-Loop Pause/Resume (`Ctrl+Alt+Space`)**: Hit the global hotkey anytime during a CAPTCHA, login prompt, or wrong turn to take back your mouse, fix it manually, and press again to recapture & resume without losing task state.
2. **Dual-Node Context Bridge & COM Error Translator**: Bridges Master Vision Planner and Fast Coder with structured diagnostic envelopes (including decoded Win32/COM HRESULT codes like `0x800A03EC`) and automatic escalation to prevent blind retry loops.
3. **Per-Monitor DPI-Aware SoM + Hybrid Vision Grid Fallback**: Normalizes coordinates across mixed-scaling displays (e.g., 150% laptop + 100% external monitor) and falls back to an `A1–H6` visual coordinate grid when UIA trees are empty (Qt/OpenGL/CAD/Canvas).
4. **Copy-on-Write Workspace Snapshots & Dry-Run Guard**: Automatically snapshots target files before mutation for instant rollback, tracks COM process lifecycles, and blocks dangerous shell commands.
5. **Deterministic Skill Distillation (`skills_cache/`)**: Compiles verified runs into reusable local skills that replay in milliseconds with **zero LLM tokens**, falling back to Vision self-healing only when the UI changes.
6. **Zero-Friction GitHub Onboarding**: Works with a **single API key or local Ollama/Qwen endpoint**, includes `python run.py --doctor` preflight checks, and degrades gracefully if `pywin32`, Office, or MATLAB are not installed.

---

## Quick Start (3 Steps)

### 1. Clone & Install
```bash
git clone https://github.com/<your-username>/DesktopPilot.git
cd DesktopPilot
pip install -r requirements.txt
```

### 2. Run Interactive Setup & Preflight Doctor
```bash
python setup_wizard.py
python run.py --doctor
```

### 3. Run a Task
```bash
# Preview actions safely with Dry-Run
python run.py --task "Export sensor_log.csv summary to report.xlsx" --workspace ./workspace --dry-run

# Execute autonomously with automatic snapshot & skill distillation
python run.py --task "Organize Downloads PDFs into dated folders" --workspace ./workspace

# Rollback last task if needed
python run.py --rollback <task_id>
```

---

## License

Released under the [MIT License](LICENSE).
