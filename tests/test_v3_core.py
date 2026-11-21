"""Comprehensive Unit Tests for All 6 DesktopPilot v3.0 Upgrades."""

import json
import tempfile
import unittest
from pathlib import Path

from desktop_pilot.context_bridge import DiagnosticHistory, ExecutionDiagnostic, decode_hresult
from desktop_pilot.doctor import run_preflight_checks
from desktop_pilot.grounding_som import (
    GroundingEngine,
    UIElementBox,
    deduplicate_boxes,
    normalize_dpi_point,
)
from desktop_pilot.hotkey_interrupt import ExecutionState, HotkeyInterruptController
from desktop_pilot.llm_router import LLMRouter
from desktop_pilot.sandbox_guard import SandboxGuard
from desktop_pilot.skill_distiller import DistilledStep, SkillDistiller


class TestDesktopPilotV3(unittest.TestCase):
    def test_1_hotkey_pause_and_recapture_resume(self):
        ctrl = HotkeyInterruptController()
        self.assertEqual(ctrl.state, ExecutionState.RUNNING)
        self.assertFalse(ctrl.wait_if_paused())

        self.assertEqual(ctrl.toggle_pause(), ExecutionState.PAUSED)
        self.assertEqual(ctrl.toggle_pause(), ExecutionState.RESUMING_RECAPTURE)
        self.assertTrue(ctrl.wait_if_paused())
        self.assertEqual(ctrl.state, ExecutionState.RUNNING)

    def test_2_com_hresult_decoder_and_escalation(self):
        hint = decode_hresult("pywintypes.com_error: (-2146827284, 'Exception occurred.', None, None)")
        self.assertIsNotNone(hint)
        self.assertIn("0x800A03EC", hint)

        history = DiagnosticHistory(max_coder_retries=2)
        d1 = ExecutionDiagnostic(1, "Write Excel summary", "com_python", "ws.Range('A0')", "0x800A03EC", attempt=1)
        d3 = ExecutionDiagnostic(1, "Write Excel summary", "com_python", "ws.Range('A0')", "0x800A03EC", attempt=3)
        self.assertFalse(history.record(d1))
        self.assertTrue(history.record(d3))
        self.assertIn("ESCALATION", d3.to_planner_escalation_digest())

    def test_3_dpi_normalization_and_grid_fallback(self):
        self.assertEqual(normalize_dpi_point(150, 300, source_scale=1.5, target_scale=1.0), (100, 200))

        dup_boxes = [
            UIElementBox(1, "Pane1", "Pane", 10, 10, 110, 110),
            UIElementBox(2, "PaneOverlay", "Pane", 11, 11, 110, 110),
        ]
        cleaned = deduplicate_boxes(dup_boxes)
        self.assertEqual(len(cleaned), 1)

        engine = GroundingEngine(grid_fallback_threshold=4)
        res = engine.ground_screen(raw_uia_boxes=cleaned, screen_size=(1920, 1080))
        self.assertEqual(res["mode"], "vision_grid_fallback")
        self.assertEqual(len(res["elements"]), 48)

    def test_4_workspace_snapshot_rollback_and_shell_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "work"
            ws.mkdir()
            target = ws / "data.txt"
            target.write_text("ORIGINAL_CONTENT", encoding="utf-8")

            guard = SandboxGuard(snapshot_root=str(Path(tmp) / "snaps"))
            self.assertFalse(guard.validate_shell_command("rm -rf /").allowed)
            self.assertTrue(guard.validate_shell_command("python sim/arm_kinematics_demo.py").allowed)

            sb = guard.create_snapshot("task_001", str(ws))
            self.assertIsNotNone(sb)
            target.write_text("CORRUPTED_PARTIAL_WRITE", encoding="utf-8")
            (ws / "temp_junk.py").write_text("print(1)", encoding="utf-8")

            ok, _ = guard.rollback("task_001")
            self.assertTrue(ok)
            self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL_CONTENT")
            self.assertFalse((ws / "temp_junk.py").exists())

    def test_5_skill_distillation_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            distiller = SkillDistiller(cache_dir=tmp)
            steps = [DistilledStep(1, "shell", {"command": "echo hello"})]
            distiller.save_verified_trajectory("Daily Export", "", steps)

            cached = distiller.lookup("Daily Export")
            self.assertIsNotNone(cached)
            ok, msg = distiller.replay_skill(cached, lambda s: (True, "ok"))
            self.assertTrue(ok)
            self.assertIn("0 LLM tokens", msg)

    def test_6_single_endpoint_fallback_and_doctor(self):
        cfg = json.loads(Path("config.example.json").read_text(encoding="utf-8"))
        cfg["models"]["planner"]["api_key"] = "sk-test-only-one-key"
        router = LLMRouter(cfg)
        self.assertTrue(router.single_endpoint_active)
        self.assertEqual(router.fast_coder.api_key, "sk-test-only-one-key")

        _, lines = run_preflight_checks("nonexistent_config.json")
        self.assertTrue(any("Python" in l for l in lines))


if __name__ == "__main__":
    unittest.main()
