"""Vendor-Agnostic Dual-Node LLM Router with Single-Endpoint Fallback (Pain Points #2 & #6)."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ModelEndpoint:
    provider: str
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.1
    enabled: bool = True

    @property
    def is_configured(self) -> bool:
        if not self.enabled:
            return False
        if not self.base_url or not self.model:
            return False
        if self.api_key in ("", "YOUR_PLANNER_API_KEY", "YOUR_CODER_API_KEY", None):
            return False
        return True


class LLMRouter:
    def __init__(self, config: Dict[str, Any]) -> None:
        models_cfg = config.get("models", {})
        planner_raw = models_cfg.get("planner", {})
        coder_raw = models_cfg.get("fast_coder", {})

        self.planner = ModelEndpoint(
            provider=planner_raw.get("provider", "openai_compatible"),
            base_url=planner_raw.get("base_url", "https://api.openai.com/v1").rstrip("/"),
            api_key=planner_raw.get("api_key", ""),
            model=planner_raw.get("model", "gpt-4o"),
            temperature=float(planner_raw.get("temperature", 0.1)),
            enabled=bool(planner_raw.get("enabled", True)),
        )
        self.fast_coder = ModelEndpoint(
            provider=coder_raw.get("provider", "openai_compatible"),
            base_url=coder_raw.get("base_url", "http://127.0.0.1:11434/v1").rstrip("/"),
            api_key=coder_raw.get("api_key", ""),
            model=coder_raw.get("model", "qwen2.5-coder:3b"),
            temperature=float(coder_raw.get("temperature", 0.0)),
            enabled=bool(coder_raw.get("enabled", False)),
        )

        self.single_endpoint_active = False
        if config.get("single_endpoint_fallback", True):
            if self.planner.is_configured and not self.fast_coder.is_configured:
                self.fast_coder = self.planner
                self.single_endpoint_active = True
            elif self.fast_coder.is_configured and not self.planner.is_configured:
                self.planner = self.fast_coder
                self.single_endpoint_active = True

        proxy_cfg = config.get("proxy", {})
        self.proxies: Optional[Dict[str, str]] = None
        if proxy_cfg.get("enabled"):
            self.proxies = {
                "http": proxy_cfg.get("http", ""),
                "https": proxy_cfg.get("https", ""),
            }

    def chat(
        self,
        role: str,
        messages: List[Dict[str, Any]],
        response_format_json: bool = False,
        timeout: int = 45,
    ) -> str:
        endpoint = self.planner if role == "planner" else self.fast_coder
        if not endpoint.is_configured:
            raise RuntimeError(
                f"LLM endpoint for role '{role}' is not configured. Run `python setup_wizard.py` first."
            )

        url = f"{endpoint.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {endpoint.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": endpoint.model,
            "messages": messages,
            "temperature": endpoint.temperature,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        body_bytes = json.dumps(payload).encode("utf-8")
        try:
            import requests  # type: ignore

            resp = requests.post(
                url,
                headers=headers,
                data=body_bytes,
                proxies=self.proxies,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except ImportError:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            opener = (
                urllib.request.build_opener(urllib.request.ProxyHandler(self.proxies))
                if self.proxies
                else urllib.request.build_opener()
            )
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

        return data["choices"][0]["message"]["content"]
