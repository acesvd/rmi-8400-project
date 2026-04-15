from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from ..config import (
    OLLAMA_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_EXTRACT_MODEL,
    OLLAMA_LETTER_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
)


@dataclass
class OllamaConfig:
    base_url: str = OLLAMA_BASE_URL
    api_key: str = OLLAMA_API_KEY
    chat_model: str = OLLAMA_CHAT_MODEL
    extract_model: str = OLLAMA_EXTRACT_MODEL
    letter_model: str = OLLAMA_LETTER_MODEL
    timeout_seconds: int = OLLAMA_TIMEOUT_SECONDS


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig()
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if self.config.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.config.api_key}"})

    def _is_cloud_base(self) -> bool:
        netloc = urlparse(self.config.base_url).netloc.lower()
        return netloc.endswith("ollama.com")

    def _normalize_model_name(self, model: str) -> str:
        # Ollama Cloud direct API expects canonical model names (for example gpt-oss:20b).
        # If callers pass a local cloud-offload alias (for example gpt-oss:20b-cloud), map it.
        cleaned = (model or "").strip()
        if self._is_cloud_base() and cleaned.endswith("-cloud"):
            return cleaned[: -len("-cloud")]
        return cleaned

    def is_available(self) -> bool:
        try:
            r = self.session.get(f"{self.config.base_url}/api/tags", timeout=4)
            return r.status_code == 200
        except Exception:
            return False

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = self.session.post(
            f"{self.config.base_url}{path}",
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        r.raise_for_status()
        return dict(r.json())

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = (text or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return text

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float = 0.2,
        format_json: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._normalize_model_name(model),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"

        body = self._post("/api/generate", payload)
        return self._strip_fences(str(body.get("response", "")).strip())

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.2,
    ) -> str:
        payload = {
            "model": self._normalize_model_name(model),
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        body = self._post("/api/chat", payload)
        msg = body.get("message") or {}
        return self._strip_fences(str(msg.get("content", "")).strip())

    def generate_json(self, *, prompt: str, model: str, temperature: float = 0.1) -> dict[str, Any]:
        raw = self.generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
            format_json=True,
        )
        if not raw:
            raise ValueError("Empty JSON response from Ollama")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = json.loads(self._strip_fences(raw))
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object from Ollama")
        return parsed
