"""Deterministic Skill Distillation & Replay Cache (Pain Point #5)."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


def normalize_intent_slug(task_prompt: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", task_prompt.strip().lower()).strip("_")
    digest = hashlib.sha1(task_prompt.strip().lower().encode("utf-8")).hexdigest()[:8]
    prefix = cleaned[:36] if cleaned else "task"
    return f"{prefix}_{digest}"


@dataclass
class DistilledStep:
    step_index: int
    action_type: str
    payload: Dict[str, Any]
    expected_window: str = ""
    post_condition: str = ""


@dataclass
class DistilledSkill:
    skill_id: str
    task_prompt: str
    target_window: str
    steps: List[DistilledStep]
    created_at: str
    hit_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "task_prompt": self.task_prompt,
            "target_window": self.target_window,
            "created_at": self.created_at,
            "hit_count": self.hit_count,
            "steps": [asdict(s) for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DistilledSkill":
        steps = [DistilledStep(**s) for s in data.get("steps", [])]
        return cls(
            skill_id=data["skill_id"],
            task_prompt=data["task_prompt"],
            target_window=data.get("target_window", ""),
            steps=steps,
            created_at=data.get("created_at", ""),
            hit_count=data.get("hit_count", 0),
        )


class SkillDistiller:
    def __init__(self, cache_dir: str = "skills_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def lookup(self, task_prompt: str, active_window: str = "") -> Optional[DistilledSkill]:
        slug = normalize_intent_slug(task_prompt)
        skill_path = self.cache_dir / f"{slug}.json"
        if not skill_path.exists():
            return None
        skill = DistilledSkill.from_dict(json.loads(skill_path.read_text(encoding="utf-8")))
        if skill.target_window and active_window and skill.target_window.lower() not in active_window.lower():
            return None
        return skill

    def save_verified_trajectory(
        self,
        task_prompt: str,
        target_window: str,
        steps: List[DistilledStep],
    ) -> DistilledSkill:
        slug = normalize_intent_slug(task_prompt)
        skill = DistilledSkill(
            skill_id=slug,
            task_prompt=task_prompt,
            target_window=target_window,
            steps=steps,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            hit_count=0,
        )
        skill_path = self.cache_dir / f"{slug}.json"
        skill_path.write_text(json.dumps(skill.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return skill

    def replay_skill(
        self,
        skill: DistilledSkill,
        step_runner: Callable[[DistilledStep], Tuple[bool, str]],
    ) -> Tuple[bool, str]:
        for step in skill.steps:
            ok, msg = step_runner(step)
            if not ok:
                return False, f"Skill drift at step {step.step_index} ({step.action_type}): {msg}"

        skill.hit_count += 1
        skill_path = self.cache_dir / f"{skill.skill_id}.json"
        skill_path.write_text(json.dumps(skill.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return True, f"Replayed distilled skill '{skill.skill_id}' ({len(skill.steps)} steps, 0 LLM tokens)."
