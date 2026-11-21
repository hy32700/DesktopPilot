"""DesktopPilot v3.0 CLI Entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from desktop_pilot.agent_engine import AgentEngine
from desktop_pilot.doctor import run_preflight_checks
from desktop_pilot.sandbox_guard import SandboxGuard


def load_config(config_path: str) -> dict:
    p = Path(config_path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    example = Path("config.example.json")
    if example.exists():
        return json.loads(example.read_text(encoding="utf-8"))
    raise FileNotFoundError("Neither config.json nor config.example.json was found.")


def main() -> int:
    parser = argparse.ArgumentParser(description="DesktopPilot v3.0 Autonomous Desktop Agent")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--doctor", action="store_true", help="Run environment preflight diagnostics")
    parser.add_argument("--task", default="", help="Natural language task prompt")
    parser.add_argument("--workspace", default="", help="Target workspace directory for snapshot protection")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without mutating disk state")
    parser.add_argument("--rollback", default="", help="Rollback workspace to given snapshot task_id")
    args = parser.parse_args()

    if args.doctor:
        ok, report_lines = run_preflight_checks(args.config)
        print("\n".join(report_lines))
        return 0 if ok else 1

    if args.rollback:
        guard = SandboxGuard()
        ok, msg = guard.rollback(args.rollback)
        print(msg)
        return 0 if ok else 1

    if not args.task:
        parser.print_help()
        return 1

    cfg = load_config(args.config)
    if args.dry_run:
        cfg.setdefault("execution", {})["dry_run"] = True

    engine = AgentEngine(cfg)
    result = engine.run_task(task_prompt=args.task, workspace_dir=args.workspace or None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
