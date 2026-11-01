"""Shared Gnani HTTP transport: auth header, single-flight gate, credit guard, retries, error
mapping and logging. Logs endpoint/status/latency/request_id only; never the key or audio."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx

from app.core.logging import get_logger
from app.voice.credit_guard import CreditGuard
from app.voice.errors import GnaniError, map_error
from app.voice.tts_queue import SingleFlight

log = get_logger(__name__)

Service = Literal["stt", "tts"]
DEFAULT_BACKOFF_S: tuple[float, ...] = (0.2, 0.4, 0.8)


def _jitter(base: float) -> float:
    return base * random.uniform(0.75, 1.25)  # noqa: S311  (not crypto)


def _safe_json(content: bytes) -> Any:
    try:
        return json.loads(content)
    except ValueError:
        return None


class GnaniTransport:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        gate: SingleFlight,
        guard: CreditGuard,
        max_retries: int = 2,
        backoff_s: tuple[float, ...] = DEFAULT_BACKOFF_S,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not api_key:
            raise GnaniError("auth", "GNANI_API_KEY is not set")
        self._client = client
        self._api_key = api_key
        self.gate = gate
        self.guard = guard
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self._sleep = sleep

    def _headers(self, request_id: str | None) -> dict[str, str]:
        h = {"X-API-Key-ID": self._api_key}
        if request_id:
            h["X-API-Request-ID"] = request_id
        return h

    async def _backoff(self, attempt: int) -> None:
        base = self.backoff_s[min(attempt, len(self.backoff_s) - 1)]
        await self._sleep(_jitter(base))

    def _log(self, service: Service, path: str, status: int | str, t0: float, attempt: int,
             request_id: str | None) -> None:  # fmt: skip
        log.info(
            "gnani_call",
            service=service,
            endpoint=path,
            status=status,
            latency_ms=round((time.perf_counter() - t0) * 1000),
            attempt=attempt,
            request_id=request_id,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        service: Service,
        timeout_s: float,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Buffered request. Retries 429/5xx/network/timeouts up to `max_retries` times."""
        await self.guard.consume(service)
        async with self.gate.slot():
            attempt = 0
            while True:
                t0 = time.perf_counter()
                err: GnaniError
                try:
                    r = await self._client.request(
                        method, path, headers=self._headers(request_id), timeout=timeout_s, **kwargs
                    )
                except httpx.TimeoutException as e:
                    self._log(service, path, "timeout", t0, attempt, request_id)
                    err = GnaniError("timeout", type(e).__name__)
                except httpx.TransportError as e:
                    self._log(service, path, "network_error", t0, attempt, request_id)
                    err = GnaniError("upstream", f"network: {type(e).__name__}")
                else:
                    self._log(service, path, r.status_code, t0, attempt, request_id)
                    if r.status_code < 400:
                        return r
                    err = map_error(r.status_code, _safe_json(r.content))
                if not err.retryable or attempt >= self.max_retries:
                    raise err
                await self._backoff(attempt)
                attempt += 1

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        path: str,
        *,
        service: Service,
        timeout_s: float,
        request_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[httpx.Response]:
        """Streaming request (SSE). Retries only while establishing the response; the gate is
        held until the body is fully consumed, because the request is 'active' until then."""
        await self.guard.consume(service)
        async with self.gate.slot():
            attempt = 0
            while True:
                t0 = time.perf_counter()
                err: GnaniError
                response: httpx.Response | None = None
                try:
                    req = self._client.build_request(
                        method, path, headers=self._headers(request_id), timeout=timeout_s, **kwargs
                    )
                    response = await self._client.send(req, stream=True)
                except httpx.TimeoutException as e:
                    self._log(service, path, "timeout", t0, attempt, request_id)
                    err = GnaniError("timeout", type(e).__name__)
                except httpx.TransportError as e:
                    self._log(service, path, "network_error", t0, attempt, request_id)
                    err = GnaniError("upstream", f"network: {type(e).__name__}")
                else:
                    self._log(service, path, response.status_code, t0, attempt, request_id)
                    if response.status_code < 400:
                        break
                    body = await response.aread()
                    await response.aclose()
                    err = map_error(response.status_code, _safe_json(body))
                if not err.retryable or attempt >= self.max_retries:
                    raise err
                await self._backoff(attempt)
                attempt += 1
            assert response is not None  # loop only breaks on a successful response
            try:
                yield response
            finally:
                await response.aclose()
