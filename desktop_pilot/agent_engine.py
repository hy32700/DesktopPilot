"""DesktopPilot v3.0 Core Orchestration Engine."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from desktop_pilot.context_bridge import DiagnosticHistory, ExecutionDiagnostic
from desktop_pilot.executor import HybridExecutor
from desktop_pilot.grounding_som import GroundingEngine
from desktop_pilot.hotkey_interrupt import HotkeyInterruptController
from desktop_pilot.llm_router import LLMRouter
from desktop_pilot.reporter import MarkdownReporter
from desktop_pilot.sandbox_guard import SandboxGuard
from desktop_pilot.skill_distiller import DistilledStep, SkillDistiller


class AgentEngine:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        exec_cfg = config.get("execution", {})
        safety_cfg = config.get("safety", {})

        self.max_steps = int(exec_cfg.get("max_steps", 25))
        self.dry_run = bool(exec_cfg.get("dry_run", False))
        self.enable_snapshots = bool(exec_cfg.get("enable_snapshots", True))
        self.enable_skill_distillation = bool(exec_cfg.get("enable_skill_distillation", True))

        self.router = LLMRouter(config)
        self.guard = SandboxGuard(
            blocked_patterns=safety_cfg.get("blocked_shell_patterns"),
            protected_paths=safety_cfg.get("protected_paths"),
        )
        self.executor = HybridExecutor(self.guard, dry_run=self.dry_run)
        self.grounding = GroundingEngine(
            max_elements=int(exec_cfg.get("som_max_elements", 80)),
            grid_fallback_threshold=int(exec_cfg.get("grid_fallback_threshold", 4)),
        )
        self.distiller = SkillDistiller()
        self.reporter = MarkdownReporter()
        self.diagnostics = DiagnosticHistory(
            max_coder_retries=int(exec_cfg.get("max_coder_retries", 2))
        )
        self.hotkey = HotkeyInterruptController(
            hotkey_label=exec_cfg.get("hotkey_pause", "Ctrl+Alt+Space")
        )

    def run_task(
        self,
        task_prompt: str,
        workspace_dir: Optional[str] = None,
        planned_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        task_id = f"dp3_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        steps_log: List[Dict[str, Any]] = []
        snapshot_id = ""

        if self.enable_snapshots and workspace_dir and not self.dry_run:
            sandbox = self.guard.create_snapshot(task_id, workspace_dir)
            if sandbox:
                snapshot_id = sandbox.task_id

        if self.enable_skill_distillation and not self.dry_run:
            cached = self.distiller.lookup(task_prompt)
            if cached:
                ok, summary = self.distiller.replay_skill(
                    cached,
                    lambda st: (
                        lambda res: (res.success, res.output if res.success else res.error)
                    )(self.executor.execute_step(st.action_type, st.payload)),
                )
                if ok:
                    steps_log.append(
                        {"step": 1, "action": "skill_replay", "success": True, "detail": summary}
                    )
                    report_path = self.reporter.write_report(
                        task_id, task_prompt, "COMPLETED_VIA_SKILL_CACHE", "deterministic_skill", steps_log, snapshot_id
                    )
                    return {
                        "task_id": task_id,
                        "status": "COMPLETED_VIA_SKILL_CACHE",
                        "mode": "deterministic_skill",
                        "snapshot_id": snapshot_id,
                        "report_path": str(report_path),
                        "detail": summary,
                    }

        self.hotkey.start()
        verified_trajectory: List[DistilledStep] = []
        try:
            grounding_ctx = self.grounding.ground_screen()
            steps_to_run = planned_steps or self._request_plan_from_llm(task_prompt, grounding_ctx)

            for idx, step_spec in enumerate(steps_to_run[: self.max_steps], start=1):
                recaptured = self.hotkey.wait_if_paused()
                if recaptured:
                    grounding_ctx = self.grounding.ground_screen()

                action_type = step_spec.get("action_type", "shell")
                payload = step_spec.get("payload", {})
                intent = step_spec.get("intent", task_prompt)

                res = self.executor.execute_step(action_type, payload)
                if res.success:
                    steps_log.append(
                        {"step": idx, "action": action_type, "success": True, "detail": res.output}
                    )
                    verified_trajectory.append(
                        DistilledStep(step_index=idx, action_type=action_type, payload=payload)
                    )
                else:
                    diag = ExecutionDiagnostic(
                        step_index=idx,
                        planner_intent=intent,
                        action_type=action_type,
                        generated_payload=json.dumps(payload, ensure_ascii=False),
                        error_message=res.error,
                        stderr_tail=res.stderr_tail,
                        attempt=1,
                    )
                    self.diagnostics.record(diag)
                    steps_log.append(
                        {
                            "step": idx,
                            "action": action_type,
                            "success": False,
                            "detail": diag.to_planner_escalation_digest(),
                        }
                    )
                    report_path = self.reporter.write_report(
                        task_id, task_prompt, "FAILED_WITH_DIAGNOSTIC", grounding_ctx["mode"], steps_log, snapshot_id
                    )
                    return {
                        "task_id": task_id,
                        "status": "FAILED_WITH_DIAGNOSTIC",
                        "mode": grounding_ctx["mode"],
                        "snapshot_id": snapshot_id,
                        "report_path": str(report_path),
                        "diagnostic": diag.to_planner_escalation_digest(),
                    }

            if self.enable_skill_distillation and verified_trajectory and not self.dry_run:
                self.distiller.save_verified_trajectory(
                    task_prompt=task_prompt,
                    target_window="",
                    steps=verified_trajectory,
                )

            final_status = "DRY_RUN_PREVIEWED" if self.dry_run else "COMPLETED"
            report_path = self.reporter.write_report(
                task_id, task_prompt, final_status, grounding_ctx["mode"], steps_log, snapshot_id
            )
            return {
                "task_id": task_id,
                "status": final_status,
                "mode": grounding_ctx["mode"],
                "snapshot_id": snapshot_id,
                "report_path": str(report_path),
                "steps_executed": len(steps_log),
            }
        finally:
            self.hotkey.stop()

    def _request_plan_from_llm(
        self,
        task_prompt: str,
        grounding_ctx: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        system_prompt = (
            "You are DesktopPilot v3.0 Master Planner. Output a JSON object with key 'steps', "
            "each containing 'intent', 'action_type' ('shell' | 'com_python' | 'uia_click' | 'uia_type'), "
            "and 'payload'."
        )
        user_msg = json.dumps(
            {"task": task_prompt, "grounding_mode": grounding_ctx["mode"]},
            ensure_ascii=False,
        )
        raw = self.router.chat(
            role="planner",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            response_format_json=True,
        )
        parsed = json.loads(raw)
        return parsed.get("steps", [])
