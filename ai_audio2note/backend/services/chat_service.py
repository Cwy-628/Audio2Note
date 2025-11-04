"""Minimal client for talking with external LLM APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import requests


class LLMError(RuntimeError):
    """Raised when the LLM service returns an error."""


@dataclass
class ChatMessage:
    role: str
    content: str


class ChatService:
    """Simple REST client for DeepSeek style chat completions."""

    DEFAULT_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "deepseek-chat"):
        if not api_key:
            raise ValueError("API Key 不能为空")
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_ENDPOINT
        self.model = model

    def chat(self, history: list[ChatMessage], user_message: str, temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in history
            ] + [{"role": "user", "content": user_message}],
            "temperature": temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(self.base_url, headers=headers, data=json.dumps(payload), timeout=60)
        if response.status_code != 200:
            raise LLMError(f"调用大模型失败: HTTP {response.status_code} - {response.text}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:  # pragma: no cover - API contract
            raise LLMError(f"解析大模型响应失败: {data}") from exc


__all__ = ["ChatService", "ChatMessage", "LLMError"]

