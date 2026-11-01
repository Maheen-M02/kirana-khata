"""Golden-set loader + scorer shared by the offline gate (rules) and the live Evon eval."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.nlu.resolver import normalise_name
from app.nlu.resolver import score as name_score
from app.nlu.schema import MONEY_INTENTS, ParsedIntent

GOLDEN_PATH = Path(__file__).with_name("golden_utterances.yaml")


@dataclass(frozen=True)
class Case:
    transcript: str
    intent: str
    customer: str | None
    amount_paise: int | None
    tags: tuple[str, ...]


def load_cases(path: Path = GOLDEN_PATH) -> list[Case]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Case(
            transcript=c["transcript"] or "",
            intent=c["expected"]["intent"],
            customer=c["expected"].get("customer"),
            amount_paise=c["expected"].get("amount_paise"),
            tags=tuple(c.get("tags", [])),
        )
        for c in raw
    ]


@dataclass
class Report:
    total: int = 0
    intent_ok: int = 0
    customer_ok: int = 0
    money_cases: int = 0
    amount_ok: int = 0
    amount_flagged: int = 0
    amount_wrong_unflagged: list[str] = field(default_factory=list)
    intent_fail: list[str] = field(default_factory=list)
    customer_fail: list[str] = field(default_factory=list)
    by_tag: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))

    @property
    def intent_accuracy(self) -> float:
        return self.intent_ok / self.total if self.total else 0.0

    @property
    def customer_accuracy(self) -> float:
        return self.customer_ok / self.total if self.total else 0.0

    def table(self) -> str:
        lines = [
            f"intent accuracy  : {self.intent_ok}/{self.total} = {self.intent_accuracy:.1%}",
            f"customer accuracy: {self.customer_ok}/{self.total} = {self.customer_accuracy:.1%}",
            f"amounts (money)  : {self.amount_ok} exact, {self.amount_flagged} flagged, "
            f"{len(self.amount_wrong_unflagged)} WRONG+UNFLAGGED of {self.money_cases}",
            "by tag:",
        ]
        for tag, (ok, n) in sorted(self.by_tag.items()):
            lines.append(f"  {tag:12} {ok:3}/{n:<3} {ok / n:6.1%}")
        for label, fails in (("intent fails", self.intent_fail),
                             ("customer fails", self.customer_fail),
                             ("amount wrong+unflagged", self.amount_wrong_unflagged)):  # fmt: skip
            if fails:
                lines.append(f"{label}:")
                lines += [f"  - {f}" for f in fails]
        return "\n".join(lines)


def score(cases: list[Case], results: list[ParsedIntent]) -> Report:
    rep = Report()
    for case, got in zip(cases, results, strict=True):
        rep.total += 1
        ok = got.intent == case.intent
        rep.intent_ok += ok
        if not ok:
            rep.intent_fail.append(f"{case.transcript!r}: want {case.intent}, got {got.intent}")
        for tag in case.tags:
            rep.by_tag[tag][0] += ok
            rep.by_tag[tag][1] += 1
        want_c = case.customer
        got_c = normalise_name(got.customer) if got.customer else None
        # Same fuzzy+phonetic matcher the resolver uses ("varma" ~ "verma").
        cust_ok = (want_c is None and got_c is None) or (
            want_c is not None and got_c is not None and name_score(want_c, got_c) >= 85
        )
        if case.intent not in ("credit_sale", "payment_received", "query_balance", "cash_sale"):
            cust_ok = True  # customer irrelevant for these intents
        rep.customer_ok += cust_ok
        if not cust_ok:
            rep.customer_fail.append(f"{case.transcript!r}: want {want_c}, got {got_c}")
        if case.intent in MONEY_INTENTS:
            rep.money_cases += 1
            if got.amount_paise == case.amount_paise:
                rep.amount_ok += 1
            elif got.amount_uncertain:
                rep.amount_flagged += 1
            else:
                rep.amount_wrong_unflagged.append(
                    f"{case.transcript!r}: want {case.amount_paise}, got {got.amount_paise} {got.flags}"
                )
    return rep
