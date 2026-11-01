"""NLU data contracts. `EvonOutput` is what the LLM must return (validated, never trusted with
money); `ParsedIntent` is what the rest of the app consumes (amounts in integer paise)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intent = Literal[
    "credit_sale",
    "cash_sale",
    "payment_received",
    "query_balance",
    "query_sales_today",
    "query_dues_list",
    "undo_last",
    "confirm_yes",
    "confirm_no",
    "unknown",
]
MONEY_INTENTS: frozenset[str] = frozenset({"credit_sale", "cash_sale", "payment_received"})
NEEDS_CUSTOMER: frozenset[str] = frozenset({"credit_sale", "payment_received", "query_balance"})
NluSource = Literal["evon", "rules", "hybrid"]

MAX_AMOUNT_PAISE = 1_00_00_000_00  # ₹1 crore: anything above is a mis-hear
LARGE_AMOUNT_PAISE = 50_000_00  # > ₹50,000 needs an extra confirmation

# Flags that mean "read the amount back explicitly / ask" (all money is confirmed anyway).
AMOUNT_UNCERTAIN_FLAGS: frozenset[str] = frozenset(
    {
        "amount_missing",
        "amount_mismatch",
        "multiple_amounts",
        "two_amounts",
        "corrected",
        "amount_unmarked",
        "low_confidence",
        "large_amount",
        "evon_amount_only",
    }
)


class EvonItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=60)
    qty: Decimal | None = Field(default=None, ge=0, le=10_000)
    unit: str | None = Field(default=None, max_length=20)


class EvonOutput(BaseModel):
    """Exact JSON shape the Evon prompt asks for. Extra keys are ignored, wrong types fail."""

    model_config = ConfigDict(extra="ignore")
    intent: Intent
    customer: str | None = Field(default=None, max_length=80)
    items: list[EvonItem] = Field(default_factory=list, max_length=20)
    amount_rupees: Decimal | None = Field(default=None, ge=0, le=Decimal(MAX_AMOUNT_PAISE) / 100)
    amount_text: str | None = Field(default=None, max_length=120)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("customer", "amount_text")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() or None if isinstance(v, str) else v


class Item(BaseModel):
    name: str
    qty: Decimal | None = None
    unit: str | None = None


class ParsedIntent(BaseModel):
    intent: Intent
    customer: str | None = None  # as spoken (romanised); resolved to an id later
    items: list[Item] = Field(default_factory=list)
    amount_paise: int | None = Field(default=None, ge=0, le=MAX_AMOUNT_PAISE)
    amount_text: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: NluSource
    flags: list[str] = Field(default_factory=list)
    transcript: str = ""

    @property
    def is_money(self) -> bool:
        return self.intent in MONEY_INTENTS

    @property
    def needs_confirmation(self) -> bool:
        """Nothing touches the ledger without a 'haan'. Queries are read-only."""
        return self.is_money or self.intent == "undo_last"

    @property
    def amount_uncertain(self) -> bool:
        return self.amount_paise is None or bool(AMOUNT_UNCERTAIN_FLAGS & set(self.flags))


class NluContext(BaseModel):
    """What the parser may know beyond the transcript."""

    known_customers: list[str] = Field(default_factory=list)  # display names + aliases
    awaiting_confirmation: bool = False
