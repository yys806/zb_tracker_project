from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


DEEPSEEK_API_KEY = ""
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


class DeepSeekClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
        timeout_s: float = 12.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "") or DEEPSEEK_API_KEY
        self.api_base = (api_base or os.environ.get("DEEPSEEK_API_BASE", "") or DEEPSEEK_API_BASE).rstrip("/")
        self.model = model or os.environ.get("DEEPSEEK_MODEL", "") or DEEPSEEK_MODEL
        self.timeout_s = timeout_s

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.configured:
            raise ValueError("DeepSeek API key is not configured. Set DEEPSEEK_API_KEY or fill DEEPSEEK_API_KEY in ai_client.py.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek request failed: {exc.reason}") from exc

        result = json.loads(body)
        choices = result.get("choices") or []
        if not choices:
            raise RuntimeError("DeepSeek response has no choices")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not content:
            raise RuntimeError("DeepSeek response is empty")
        return str(content).strip()
