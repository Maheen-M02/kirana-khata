"""OpenAI-compatible chat client for self-hosted Evon (vLLM / SGLang / llama-server / Ollama).
Thinking is disabled for latency; structured JSON is coaxed by the prompt, then extracted."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?", re.IGNORECASE)


class EvonUnavailableError(Exception):
    """Timeout, network failure or non-2xx: the caller falls back to rules."""


class ChatModel(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str: ...


class EvonClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: float = 4.0,
        guided_json: bool = False,
    ) -> None:
        self._client = client
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self._api_key = api_key
        self.timeout_s = timeout_s
        self.guided_json = guided_json

    def body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 400,
            # vLLM/SGLang: forwarded to the chat template; turns Evon's reasoning off.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if self.guided_json:
            body["response_format"] = {"type": "json_object"}
        return body

    async def complete(self, messages: list[dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            r = await self._client.post(
                self.url, json=self.body(messages), headers=headers, timeout=self.timeout_s
            )
        except httpx.HTTPError as e:
            raise EvonUnavailableError(type(e).__name__) from e
        if r.status_code >= 400:
            raise EvonUnavailableError(f"HTTP {r.status_code}")
        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EvonUnavailableError("unexpected response shape") from e
        return str(content or "")


def extract_json(text: str) -> dict[str, Any]:
    """Strip <think> blocks and code fences, return the first balanced {...} object."""
    cleaned = _FENCE.sub("", _THINK.sub("", text))
    start = cleaned.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(cleaned[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
        start = cleaned.find("{", start + 1)
    raise ValueError("no JSON object found in model output")


class FakeEvon:
    """Canned replies keyed by transcript; a reply may be an Exception to raise. For tests."""

    def __init__(self, replies: dict[str, str | Exception | list[str | Exception]]) -> None:
        self.replies = replies
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        user_turns = [m["content"] for m in messages if m["role"] == "user"]
        retry_note = "Your last reply was invalid"
        transcript = next(t for t in reversed(user_turns) if not t.startswith(retry_note))
        reply = self.replies.get(transcript, EvonUnavailableError("no canned reply"))
        if isinstance(reply, list):
            reply = reply.pop(0) if len(reply) > 1 else reply[0]
        if isinstance(reply, Exception):
            raise reply
        return reply
