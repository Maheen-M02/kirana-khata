"""Evon adapter + HybridParser with FakeEvon (canned replies). No network, no GPU."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx
from pydantic import ValidationError

from app.nlu.evon_client import EvonClient, EvonUnavailableError, FakeEvon, extract_json
from app.nlu.parser import EvonParser, HybridParser, RulesParser
from app.nlu.prompts import FEW_SHOT, build_messages
from app.nlu.schema import EvonOutput, NluContext, ParsedIntent

CTX = NluContext(known_customers=["Sharma ji", "Gupta ji"])
T_CREDIT = "Sharma ji ne do kilo cheeni li, ek sau bees rupaye udhaar"


def reply(**kw: object) -> str:
    base: dict[str, object] = {"intent": "credit_sale", "customer": "Sharma ji", "items": [],
                               "amount_rupees": 120, "amount_text": "ek sau bees rupaye",
                               "confidence": 0.95}  # fmt: skip
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def hybrid(replies: dict[str, object], timeout_s: float = 4.0) -> HybridParser:
    return HybridParser(EvonParser(FakeEvon(replies), timeout_s=timeout_s))  # type: ignore[arg-type]


async def test_agreement_gives_hybrid_high_confidence() -> None:
    p = await hybrid({T_CREDIT: reply()}).parse(T_CREDIT, CTX)
    assert (p.intent, p.amount_paise, p.source) == ("credit_sale", 12000, "hybrid")
    assert p.confidence == pytest.approx(0.95)
    assert "amount_mismatch" not in p.flags
    assert p.needs_confirmation


async def test_llm_wrong_amount_is_overruled_by_rules_and_flagged() -> None:
    p = await hybrid({T_CREDIT: reply(amount_rupees=1200)}).parse(T_CREDIT, CTX)
    assert p.amount_paise == 12000  # deterministic parse wins
    assert "amount_mismatch" in p.flags
    assert p.amount_uncertain
    assert p.confidence <= 0.6


async def test_llm_invented_amount_without_backing_is_flagged() -> None:
    t = "Sharma ji ne cheeni li"
    p = await hybrid({t: reply(amount_rupees=50, amount_text=None)}).parse(t, CTX)
    assert p.amount_paise == 5000
    assert "evon_amount_only" in p.flags
    assert p.amount_uncertain


async def test_invalid_json_retries_once_with_error_then_succeeds() -> None:
    fake = FakeEvon({T_CREDIT: ["Sure! here you go", reply()]})
    p = await HybridParser(EvonParser(fake)).parse(T_CREDIT, CTX)
    assert p.source == "hybrid"
    assert len(fake.calls) == 2
    assert fake.calls[1][-1]["content"].startswith("Your last reply was invalid")


async def test_invalid_twice_falls_back_to_rules() -> None:
    p = await hybrid({T_CREDIT: ["nope", '{"intent": "bogus", "confidence": 2}']}).parse(
        T_CREDIT, CTX
    )
    assert p.source == "rules"
    assert "evon_down" in p.flags
    assert p.amount_paise == 12000
    assert p.confidence <= 0.7


async def test_evon_down_uses_rules() -> None:
    p = await hybrid({T_CREDIT: EvonUnavailableError("conn refused")}).parse(T_CREDIT, CTX)
    assert (p.intent, p.amount_paise, p.source) == ("credit_sale", 12000, "rules")


async def test_evon_timeout_uses_rules() -> None:
    class Slow:
        async def complete(self, messages: list[dict[str, str]]) -> str:
            await asyncio.sleep(1)
            return reply()

    p = await HybridParser(EvonParser(Slow(), timeout_s=0.05)).parse(T_CREDIT, CTX)
    assert p.source == "rules"


async def test_evon_unknown_but_rules_sure_uses_rules_intent() -> None:
    t = "Gupta ji ne 300 rupaye jama kiye"
    p = await hybrid({t: reply(intent="unknown", amount_rupees=None, amount_text=None,
                               confidence=0.3)}).parse(t, CTX)  # fmt: skip
    assert p.intent == "payment_received"
    assert p.amount_paise == 30000
    assert "evon_unknown" in p.flags


async def test_intent_disagreement_lowers_confidence() -> None:
    t = "Gupta ji ne 300 rupaye jama kiye"
    p = await hybrid({t: reply(customer="Gupta ji", amount_rupees=300,
                               amount_text="300 rupaye")}).parse(t, CTX)  # fmt: skip
    assert p.intent == "credit_sale"  # Evon decides wording-heavy intent...
    assert "intent_mismatch" in p.flags  # ...but the disagreement is surfaced
    assert p.confidence <= 0.7


async def test_query_has_no_amount_and_needs_no_confirmation() -> None:
    t = "aaj kitni bikri hui"
    p = await hybrid({t: reply(intent="query_sales_today", customer=None, amount_rupees=None,
                               amount_text=None)}).parse(t, CTX)  # fmt: skip
    assert p.amount_paise is None
    assert not p.needs_confirmation


async def test_rules_parser_wrapper() -> None:
    p = await RulesParser().parse(T_CREDIT, CTX)
    assert isinstance(p, ParsedIntent)
    assert p.source == "rules"


async def test_evon_only_parser_converts_rupees_to_paise() -> None:
    p = await EvonParser(FakeEvon({T_CREDIT: reply(amount_rupees=120.5)})).parse(T_CREDIT, CTX)
    assert p.amount_paise == 12050
    assert p.source == "evon"


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '<think>let me think {"no": "this"}</think>{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here is the JSON: {"a": 1} hope that helps',
        '{"a": 1, "s": "brace } inside"}',
    ],
)
def test_extract_json(text: str) -> None:
    assert extract_json(text)["a"] == 1


def test_extract_json_raises_without_object() -> None:
    with pytest.raises(ValueError, match="no JSON"):
        extract_json("I could not parse that")


def test_schema_rejects_bad_llm_output() -> None:
    with pytest.raises(ValidationError):
        EvonOutput.model_validate({"intent": "credit_sale", "confidence": 1.5})
    with pytest.raises(ValidationError):
        EvonOutput.model_validate({"intent": "steal_money", "confidence": 0.9})
    with pytest.raises(ValidationError):
        EvonOutput.model_validate({"intent": "credit_sale", "confidence": 0.9, "amount_rupees": -5})


def test_few_shots_are_schema_valid_and_prompt_lists_customers() -> None:
    for _, out in FEW_SHOT:
        EvonOutput.model_validate(out)
    msgs = build_messages("x", ["Sharma ji", "Sharma ji", "Gupta ji"])
    assert "Known customers: Sharma ji, Gupta ji" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "x"}


@respx.mock
async def test_evon_client_request_shape_and_errors() -> None:
    route = respx.post("http://evon.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": reply()}}]})
    )
    async with httpx.AsyncClient() as c:
        client = EvonClient(c, base_url="http://evon.test/v1", model="evon", api_key="k")
        out = await client.complete([{"role": "user", "content": "hi"}])
        assert json.loads(out)["intent"] == "credit_sale"
        sent = json.loads(route.calls.last.request.content)
        assert sent["chat_template_kwargs"] == {"enable_thinking": False}
        assert sent["temperature"] == 0.2
        assert sent["max_tokens"] == 400
        assert route.calls.last.request.headers["Authorization"] == "Bearer k"

        route.mock(return_value=httpx.Response(503))
        with pytest.raises(EvonUnavailableError):
            await client.complete([{"role": "user", "content": "hi"}])
        route.mock(side_effect=httpx.ConnectError("down"))
        with pytest.raises(EvonUnavailableError):
            await client.complete([{"role": "user", "content": "hi"}])
