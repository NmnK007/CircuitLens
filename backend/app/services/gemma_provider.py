"""Ollama adapter for local Gemma 4 inference.

Uses Ollama's documented /api/generate endpoint. This adapter never simulates
circuits; it only proposes image observations and explains server-generated data.
"""

import base64
import json
from typing import Any, Dict, Optional
import requests

from ..core.config import settings


class GemmaUnavailable(RuntimeError):
    pass


class GemmaProvider:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: float = 120.0):
        self.base_url = (base_url or settings.GEMMA_BASE_URL or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or settings.GEMMA_MODEL_ID
        self.timeout = timeout

    @property
    def provider(self) -> str:
        return "ollama"

    def available(self) -> bool:
        try:
            response = requests.get(self.base_url + "/api/tags", timeout=2.0)
            if response.status_code != 200:
                return False
            models = response.json().get("models", [])
            expected = self.model if ":" in self.model else self.model + ":latest"
            return any(m.get("name") in (self.model, expected) for m in models)
        except (requests.RequestException, ValueError, AttributeError):
            return False

    def generate_json(self, prompt: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 1800},
        }
        if image_bytes is not None:
            payload["images"] = [base64.b64encode(image_bytes).decode("ascii")]
        try:
            response = requests.post(self.base_url + "/api/generate", json=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
            text = body.get("response", "")
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("Gemma response must be a JSON object")
            return parsed
        except (requests.RequestException, ValueError, KeyError) as exc:
            raise GemmaUnavailable(
                "Gemma 4 is unavailable or returned invalid JSON. Start Ollama and pull the configured model."
            ) from exc
