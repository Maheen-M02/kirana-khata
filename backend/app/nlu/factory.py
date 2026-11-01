"""Build the IntentParser for NLU_MODE (rules | evon | hybrid)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings
from app.nlu.evon_client import EvonClient
from app.nlu.parser import EvonParser, HybridParser, IntentParser, RulesParser


@dataclass
class NluStack:
    parser: IntentParser
    client: httpx.AsyncClient | None = None

    async def aclose(self) -> None:
        if self.client is not None:
            await self.client.aclose()


def build_parser(settings: Settings) -> NluStack:
    if settings.nlu_mode == "rules":
        return NluStack(RulesParser())
    client = httpx.AsyncClient()
    evon = EvonParser(
        EvonClient(
            client,
            base_url=settings.evon_base_url,
            model=settings.evon_model,
            api_key=settings.evon_api_key.get_secret_value(),
            timeout_s=settings.evon_timeout_s,
            guided_json=settings.evon_guided_json,
        ),
        timeout_s=settings.evon_timeout_s,
    )
    parser: IntentParser = evon if settings.nlu_mode == "evon" else HybridParser(evon)
    return NluStack(parser, client)
