# DesktopPilot v3.0 Product Requirements Document (PRD)

- **Version**: v3.0.0 (Open-Source Release Candidate)
- **Target Platform**: Windows 10 / Windows 11 (with cross-platform dry-run & simulation support)
- **License**: MIT
- **Core Positioning**: A vendor-agnostic, hybrid autonomous Windows desktop agent combining **Per-Monitor DPI-Aware UIA Set-of-Mark (SoM) + Grid Vision**, **Thread-Safe COM Automation (Excel / MATLAB)**, **Guarded Shell Execution**, and **Deterministic Skill Distillation**.

---

## 1. Background & Problem Statement (v0.2.0 -> v3.0.0)

While DesktopPilot v0.2.0 validated dual-node LLM routing (Master Vision Planner + Fast Coder) and UIA Set-of-Mark grounding, real-world usage exposed six critical friction points that blocked unattended reliability and open-source adoption:

1. **Mouse Hijacking & Lack of Human-in-the-Loop Pause/Resume**: Users could not pause an active run during CAPTCHAs, 2FA prompts, or trajectory drift without killing the entire process and losing state.
2. **Dual-Node Context Disconnect & Retry Loops**: When Fast Coder scripts failed locally (e.g., cryptic COM HRESULT `0x800A03EC`), Fast Coder blindly patched syntax without knowing Planner's global goal, while Planner never saw the full stack trace.
3. **UIA Blindness on Non-Native UIs & Multi-Monitor DPI Drift**: Custom-rendered viewports (Qt/OpenGL, CAD, Electron virtual lists, HTML5 Canvas) returned empty or flooded UIA trees, and mixed-DPI monitors (e.g., 150% + 100%) caused click coordinate offsets.
4. **Workspace Pollution & Irreversible Side Effects**: Long-chain tasks risked corrupting live Excel/CAD files or leaving zombie `EXCEL.EXE` / `MATLAB.exe` COM processes without rollback protection.
5. **Zero Trajectory Reuse (Paying Vision Tax Every Run)**: Recurring daily workflows re-executed the full screenshot -> SoM -> Planner -> Fast Coder loop every time instead of compiling verified runs into deterministic local skills.
6. **High First-Run Friction for GitHub Users**: New users faced missing `pywin32`/COM host dependencies, rigid dual-API-key requirements, and opaque startup errors.

---

## 2. v3.0 Core Architecture & Requirements

### FR-1: Global Hotkey Interrupt & State-Preserving Resume (`hotkey_interrupt.py`)
- **Hotkey**: Default `Ctrl+Alt+Space` (configurable via `config.json`) registered via Win32 `GetAsyncKeyState` polling loop.
- **State Machine**: `RUNNING` <-> `PAUSED` -> `RESUMING_RECAPTURE` -> `COMPLETED` / `ABORTED`.
- **Behavior**: Pressing the hotkey immediately yields mouse/keyboard control back to the user. Pressing it again triggers a fresh screenshot + UIA/Grid capture so the Planner seamlessly adapts to whatever manual fix the user performed.

### FR-2: Structured Diagnostic Context Bridge (`context_bridge.py` & `llm_router.py`)
- **Diagnostic Envelope**: Captures `step_index`, `planner_intent`, `generated_code`, `exception_type`, `hresult_decoded`, `stderr_tail`, and `active_window`.
- **Escalation Policy**: Fast Coder gets up to `max_coder_retries` (default 2) with full COM error translation; if still failing, escalates the compact diagnostic digest to Master Vision Planner to re-plan an alternative route.

### FR-3: Per-Monitor DPI Normalization & Hybrid UIA + Grid Grounding (`grounding_som.py`)
- **DPI Awareness**: Enables `PROCESS_PER_MONITOR_DPI_AWARE_V2` at startup and maps physical pixels to logical Win32 input coordinates per monitor handle.
- **Noise Suppression**: Deduplicates overlapping bounding boxes and enforces `som_max_elements` (default 80).
- **Vision Grid Fallback**: If UIA yields fewer than `grid_fallback_threshold` (default 4) valid controls (e.g., OpenGL/Qt/Canvas apps), automatically overlays a labeled `A1`–`H6` visual coordinate grid so the Vision Planner can click reliably.

### FR-4: Copy-on-Write Workspace Snapshots, Dry-Run & COM Lifecycle Guard (`sandbox_guard.py`)
- **Pre-Task Snapshots**: Backs up target files/directories into `.desktop_pilot_snapshots/<task_id>/` before execution, supporting one-command `rollback(task_id)`.
- **Dry-Run Preview (`--dry-run`)**: Prints planned actions/commands without mutating disk state.
- **COM & Shell Safety**: Tracks spawned COM process IDs for deterministic cleanup and blocks destructive shell patterns (`rm -rf`, `del /s`, `format`, `reg delete`, etc.).

### FR-5: Deterministic Skill Distillation & Visual Self-Healing (`skill_distiller.py`)
- **Skill Compilation**: Persists verified successful execution sequences to `skills_cache/<slug>.json`.
- **Fast Replay + Fallback**: Matches normalized task intent and target window class on subsequent runs, replaying deterministic steps in <200ms with **0 LLM tokens**. If a UI selector or post-condition fails, seamlessly falls back to the Vision Planner to heal and update the skill.

### FR-6: Zero-Friction Onboarding, Doctor CLI & Single-Key Fallback (`setup_wizard.py` & `doctor.py`)
- **Preflight Doctor (`python run.py --doctor`)**: Validates Python version, DPI context, optional `pywin32`/COM host apps, proxy reachability, and API configuration with actionable fix hints.
- **Single-Endpoint Fallback**: When only one API key (or a local Ollama/vLLM server) is configured, `llm_router.py` automatically routes both Planner and Fast Coder roles to that endpoint.

---

## 3. Acceptance Criteria (v3.0 Release Gate)
1. `python run.py --doctor` runs cleanly on any Windows/Linux/macOS machine without crashing even when `pywin32`, Office, or MATLAB are absent.
2. Single-key `config.json` works out-of-the-box without requiring separate Planner and Fast Coder keys.
3. Workspace snapshot + rollback restores modified files byte-for-byte.
4. Repeated identical tasks hit `skills_cache/` with zero LLM calls and automatically fall back on simulated UI drift.
5. All unit tests in `tests/test_v3_core.py` pass with 0 errors.
