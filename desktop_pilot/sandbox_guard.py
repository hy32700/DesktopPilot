"""Workspace Snapshot Backup, Dry-Run Gate & Shell/COM Safety Guard (Pain Point #4)."""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


DEFAULT_BLOCKED_PATTERNS = [
    "rm -rf",
    "del /s",
    "rmdir /s",
    "format ",
    "diskpart",
    "reg delete",
    "shutdown",
    "taskkill /f /im explorer.exe",
]


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str


@dataclass
class TaskSandbox:
    task_id: str
    workspace_dir: Path
    snapshot_root: Path
    spawned_pids: List[int] = field(default_factory=list)

    @property
    def snapshot_dir(self) -> Path:
        return self.snapshot_root / self.task_id


class SandboxGuard:
    def __init__(
        self,
        snapshot_root: str = ".desktop_pilot_snapshots",
        blocked_patterns: Optional[List[str]] = None,
        protected_paths: Optional[List[str]] = None,
    ) -> None:
        self.snapshot_root = Path(snapshot_root)
        self.blocked_patterns = [p.lower() for p in (blocked_patterns or DEFAULT_BLOCKED_PATTERNS)]
        self.protected_paths = [os.path.normcase(p) for p in (protected_paths or [])]

    def validate_shell_command(self, command: str) -> SafetyDecision:
        cmd_lower = (command or "").strip().lower()
        if not cmd_lower:
            return SafetyDecision(False, "Empty shell command rejected.")
        for pattern in self.blocked_patterns:
            if pattern in cmd_lower:
                return SafetyDecision(False, f"Blocked dangerous shell pattern: '{pattern}'")
        for ppath in self.protected_paths:
            if ppath and ppath in cmd_lower:
                return SafetyDecision(False, f"Command references protected system path: '{ppath}'")
        return SafetyDecision(True, "Command passed safety guardrail.")

    def create_snapshot(self, task_id: str, workspace_dir: str) -> Optional[TaskSandbox]:
        ws = Path(workspace_dir).resolve()
        if not ws.exists() or not ws.is_dir():
            return None

        sandbox = TaskSandbox(
            task_id=task_id,
            workspace_dir=ws,
            snapshot_root=self.snapshot_root.resolve(),
        )
        backup_files_dir = sandbox.snapshot_dir / "files"
        if sandbox.snapshot_dir.exists():
            shutil.rmtree(sandbox.snapshot_dir)
        backup_files_dir.mkdir(parents=True, exist_ok=True)

        copied_files: List[str] = []
        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if d != ".desktop_pilot_snapshots" and d != "__pycache__"]
            rel_root = Path(root).relative_to(ws)
            target_dir = backup_files_dir / rel_root
            target_dir.mkdir(parents=True, exist_ok=True)
            for fname in files:
                src_file = Path(root) / fname
                dst_file = target_dir / fname
                shutil.copy2(src_file, dst_file)
                copied_files.append(str(rel_root / fname))

        manifest = {
            "task_id": task_id,
            "workspace_dir": str(ws),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "files": copied_files,
        }
        (sandbox.snapshot_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return sandbox

    def rollback(self, task_id: str) -> Tuple[bool, str]:
        snap_dir = self.snapshot_root.resolve() / task_id
        manifest_path = snap_dir / "manifest.json"
        if not manifest_path.exists():
            return False, f"Snapshot '{task_id}' not found at {snap_dir}"

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ws = Path(manifest["workspace_dir"])
        backup_files_dir = snap_dir / "files"

        expected_rel = set(manifest.get("files", []))
        for root, dirs, files in os.walk(ws):
            dirs[:] = [d for d in dirs if d != ".desktop_pilot_snapshots"]
            rel_root = Path(root).relative_to(ws)
            for fname in files:
                rel_path = str(rel_root / fname)
                if rel_path not in expected_rel:
                    (Path(root) / fname).unlink(missing_ok=True)

        for rel_path in expected_rel:
            src = backup_files_dir / rel_path
            dst = ws / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                shutil.copy2(src, dst)

        return True, f"Workspace '{ws}' successfully rolled back to snapshot '{task_id}'."
