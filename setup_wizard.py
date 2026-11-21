"""Interactive 60-Second Onboarding Wizard for DesktopPilot v3.0 (Pain Point #6)."""

from __future__ import annotations

import json
from pathlib import Path


def run_wizard() -> None:
    print("=== DesktopPilot v3.0 Quick Setup Wizard ===")
    example_path = Path("config.example.json")
    cfg = json.loads(example_path.read_text(encoding="utf-8"))

    base_url = input("OpenAI-compatible Base URL [https://api.openai.com/v1]: ").strip()
    if base_url:
        cfg["models"]["planner"]["base_url"] = base_url

    api_key = input("API Key (single key works for both Planner & Coder): ").strip()
    if api_key:
        cfg["models"]["planner"]["api_key"] = api_key

    model = input("Planner Model Name [gpt-4o]: ").strip()
    if model:
        cfg["models"]["planner"]["model"] = model

    use_separate_coder = input("Configure a separate Fast Coder endpoint? [y/N]: ").strip().lower()
    if use_separate_coder == "y":
        cfg["models"]["fast_coder"]["enabled"] = True
        coder_url = input("Fast Coder Base URL [http://127.0.0.1:11434/v1]: ").strip()
        coder_key = input("Fast Coder API Key [ollama]: ").strip()
        coder_model = input("Fast Coder Model [qwen2.5-coder:3b]: ").strip()
        if coder_url:
            cfg["models"]["fast_coder"]["base_url"] = coder_url
        if coder_key:
            cfg["models"]["fast_coder"]["api_key"] = coder_key
        if coder_model:
            cfg["models"]["fast_coder"]["model"] = coder_model

    proxy = input("Optional HTTP/HTTPS Proxy (e.g. http://127.0.0.1:7897, Enter to skip): ").strip()
    if proxy:
        cfg["proxy"]["enabled"] = True
        cfg["proxy"]["http"] = proxy
        cfg["proxy"]["https"] = proxy

    Path("config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("Saved config.json! Run `python run.py --doctor` to verify your setup.")


if __name__ == "__main__":
    run_wizard()
