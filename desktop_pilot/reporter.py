"""Automated Markdown Execution Report Generator."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List


class MarkdownReporter:
    def __init__(self, reports_dir: str = "reports") -> None:
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def write_report(
        self,
        task_id: str,
        task_prompt: str,
        status: str,
        mode_used: str,
        steps_log: List[Dict[str, Any]],
        snapshot_id: str = "",
    ) -> Path:
        report_path = self.reports_dir / f"{task_id}_report.md"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        lines = [
            f"# DesktopPilot v3.0 Execution Report — `{task_id}`",
            "",
            f"- **Timestamp**: {timestamp}",
            f"- **Task Prompt**: {task_prompt}",
            f"- **Final Status**: `{status}`",
            f"- **Execution Mode**: `{mode_used}`",
            f"- **Workspace Snapshot ID**: `{snapshot_id or 'disabled'}`",
            "",
            "## Step-by-Step Execution Trace",
            "",
            "| Step | Action | Status | Output / Diagnostic |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for entry in steps_log:
            step_no = entry.get("step", "-")
            action = entry.get("action", "-")
            ok = "PASS" if entry.get("success") else "FAIL"
            detail = str(entry.get("detail", "")).replace("\n", " ")[:140]
            lines.append(f"| {step_no} | `{action}` | {ok} | {detail} |")

        lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path
