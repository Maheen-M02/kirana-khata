"""IntentParser implementations: RulesParser, EvonParser and HybridParser (Evon for variety,
rules for money correctness). The LLM's amount is only ever a suggestion."""

from __future__ import annotations

import asyncio
from typing import Protocol

from pydantic import ValidationError

from app.core.logging import get_logger
from app.nlu.evon_client import ChatModel, EvonUnavailableError, extract_json
from app.nlu.numbers_hi import parse_amount, to_paise
from app.nlu.prompts import build_messages
from app.nlu.rules import parse_rules
from app.nlu.schema import (
    LARGE_AMOUNT_PAISE,
    MONEY_INTENTS,
    EvonOutput,
    Item,
    NluContext,
    ParsedIntent,
)

log = get_logger(__name__)

CONFIRM_THRESHOLD = 0.75


class IntentParser(Protocol):
    async def parse(self, transcript: str, ctx: NluContext) -> ParsedIntent: ...


class RulesParser:
    async def parse(self, transcript: str, ctx: NluContext) -> ParsedIntent:
        return parse_rules(transcript, ctx)


class EvonParser:
    """Evon only: validate, retry once with the validation error, else raise."""

    def __init__(self, model: ChatModel, *, timeout_s: float = 4.0) -> None:
        self.model = model
        self.timeout_s = timeout_s

    async def raw(self, transcript: str, ctx: NluContext) -> EvonOutput:
        async with asyncio.timeout(self.timeout_s):  # total budget incl. the retry
            error: str | None = None
            for _attempt in range(2):
                text = await self.model.complete(
                    build_messages(transcript, ctx.known_customers, error)
                )
                try:
                    return EvonOutput.model_validate(extract_json(text))
                except (ValueError, ValidationError) as e:
                    error = str(e).splitlines()[0]
                    log.info("evon_invalid_output", error=error)
        raise EvonUnavailableError(f"invalid output twice: {error}")

    async def parse(self, transcript: str, ctx: NluContext) -> ParsedIntent:
        out = await self.raw(transcript, ctx)
        paise = to_paise(out.amount_rupees) if out.amount_rupees is not None else None
        return ParsedIntent(
            intent=out.intent,
            customer=out.customer,
            items=[Item(name=i.name.lower(), qty=i.qty, unit=i.unit) for i in out.items],
            amount_paise=paise,
            amount_text=out.amount_text,
            confidence=out.confidence,
            source="evon",
            transcript=transcript,
        )


class HybridParser:
    """Evon first, rules always. Rules decide money; Evon decides wording-heavy intent."""

    def __init__(self, evon: EvonParser) -> None:
        self.evon = evon

    async def parse(self, transcript: str, ctx: NluContext) -> ParsedIntent:
        rules = parse_rules(transcript, ctx)
        try:
            out = await self.evon.raw(transcript, ctx)
        except (EvonUnavailableError, TimeoutError) as e:
            log.info("evon_fallback_to_rules", reason=str(e) or type(e).__name__)
            return rules.model_copy(
                update={
                    "confidence": min(rules.confidence, 0.7),
                    "flags": [*rules.flags, "evon_down"],
                }
            )
        return merge(out, rules)


def merge(evon: EvonOutput, rules: ParsedIntent) -> ParsedIntent:
    flags = [f for f in rules.flags if f not in ("ambiguous_type",)]
    intent = evon.intent
    confidence = evon.confidence
    if intent == "unknown" and rules.intent != "unknown":
        intent, confidence = rules.intent, min(rules.confidence, 0.6)
        flags.append("evon_unknown")
    elif intent != rules.intent and rules.intent != "unknown":
        flags.append("intent_mismatch")
        confidence = min(confidence, 0.7)

    paise: int | None = None
    if intent in MONEY_INTENTS:
        evon_paise = to_paise(evon.amount_rupees) if evon.amount_rupees is not None else None
        text_paise = parse_amount(evon.amount_text)  # rules re-read Evon's quoted phrase
        rules_paise = rules.amount_paise
        if rules_paise is not None:
            paise = rules_paise
            if evon_paise is not None and evon_paise != rules_paise:
                flags.append("amount_mismatch")
        elif text_paise is not None:
            paise = text_paise
            if evon_paise is not None and evon_paise != text_paise:
                flags.append("amount_mismatch")
        elif evon_paise is not None:
            paise = evon_paise
            flags.append("evon_amount_only")  # nothing deterministic backs it: read it back
        else:
            flags.append("amount_missing")
        if paise is not None and paise > LARGE_AMOUNT_PAISE:
            flags.append("large_amount")
        if "amount_mismatch" in flags:
            confidence = min(confidence, 0.6)
    if confidence < CONFIRM_THRESHOLD and intent in MONEY_INTENTS:
        flags.append("low_confidence")

    items = (
        [Item(name=i.name.lower(), qty=i.qty, unit=i.unit) for i in evon.items]
        if evon.items
        else rules.items
    )
    return ParsedIntent(
        intent=intent,
        customer=evon.customer or rules.customer,
        items=items,
        amount_paise=paise,
        amount_text=evon.amount_text or rules.amount_text,
        confidence=confidence,
        source="hybrid",
        flags=sorted(set(flags)),
        transcript=rules.transcript,
    )
