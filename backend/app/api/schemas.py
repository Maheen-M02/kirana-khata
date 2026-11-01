"""API request/response models. Money crosses the wire as integer paise (+ a display string),
so the browser never does float arithmetic on rupees."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, StrictInt

from app.ledger.models import LedgerEntry
from app.ledger.queries import CustomerBalance, SalesSummary, format_inr


class LineInModel(BaseModel):
    item_name: str = Field(min_length=1, max_length=60)
    qty: Decimal | None = Field(default=None, ge=0, le=10_000)
    unit: str | None = Field(default=None, max_length=20)
    amount_paise: StrictInt | None = Field(default=None, gt=0)


class EntryIn(BaseModel):
    """A manual entry typed/tapped in the UI. Tapping 'save' is the explicit confirmation."""

    type: Literal["credit_sale", "cash_sale", "payment_received"]
    amount_paise: StrictInt = Field(gt=0)
    customer_id: int | None = None
    note: str | None = Field(default=None, max_length=200)
    lines: list[LineInModel] = Field(default_factory=list, max_length=20)


class CustomerIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ]{10,15}$")
    aliases: list[str] = Field(default_factory=list, max_length=10)


class AliasIn(BaseModel):
    alias: str = Field(min_length=1, max_length=80)


class LineOut(BaseModel):
    item_name: str
    qty: Decimal | None
    unit: str | None
    amount_paise: int | None


class EntryOut(BaseModel):
    id: int
    type: str
    amount_paise: int
    amount_display: str
    customer_id: int | None
    customer_name: str | None
    note: str | None
    created_at: datetime
    is_reversal: bool
    reverses_entry_id: int | None
    reversed_by: int | None
    voice_event_id: int | None
    lines: list[LineOut]

    @classmethod
    def of(cls, e: LedgerEntry, reversed_by: dict[int, int]) -> EntryOut:
        return cls(
            id=e.id,
            type=e.type.value,
            amount_paise=e.amount_paise,
            amount_display=format_inr(e.amount_paise),
            customer_id=e.customer_id,
            customer_name=e.customer.display_name if e.customer else None,
            note=e.note,
            created_at=e.created_at,
            is_reversal=e.is_reversal,
            reverses_entry_id=e.reverses_entry_id,
            reversed_by=reversed_by.get(e.id),
            voice_event_id=e.voice_event_id,
            lines=[
                LineOut(
                    item_name=ln.item_name, qty=ln.qty, unit=ln.unit, amount_paise=ln.amount_paise
                )
                for ln in e.lines
            ],
        )


class CustomerOut(BaseModel):
    id: int
    display_name: str
    aliases: list[str]
    phone: str | None
    balance_paise: int
    balance_display: str
    last_activity: datetime | None

    @classmethod
    def of(cls, b: CustomerBalance) -> CustomerOut:
        return cls(
            id=b.customer_id,
            display_name=b.display_name,
            aliases=b.aliases,
            phone=b.phone,
            balance_paise=b.balance_paise,
            balance_display=format_inr(b.balance_paise),
            last_activity=b.last_activity,
        )


class CustomerDetail(CustomerOut):
    entries: list[EntryOut]


class SalesOut(BaseModel):
    total_paise: int
    total_display: str
    cash_paise: int
    credit_paise: int
    payments_paise: int
    entries: int
    speak: str

    @classmethod
    def of(cls, s: SalesSummary, speak: str) -> SalesOut:
        return cls(
            total_paise=s.total_paise,
            total_display=format_inr(s.total_paise),
            cash_paise=s.cash_paise,
            credit_paise=s.credit_paise,
            payments_paise=s.payments_paise,
            entries=s.entries,
            speak=speak,
        )


class DuesOut(BaseModel):
    customers: list[CustomerOut]
    total_paise: int
    total_display: str
    speak: str


class UndoOut(BaseModel):
    reversal: EntryOut
    original_id: int
    speak: str
