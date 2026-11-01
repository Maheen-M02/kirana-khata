"""ORM models (MASTER_PROMPT §5). Works on SQLite (dev) and Postgres (prod).

Ledger rules enforced at three layers (service, ORM events, DB triggers in the migration):
- money is an integer number of paise (BigInteger), never a float;
- `ledger_entry` / `ledger_line` are INSERT-only: no UPDATE, no DELETE, ever;
- a correction is a *reversal entry*: same type, negative amount, `reverses_entry_id` -> original.
  (The spec's `reversed_by` is derived from that link instead of updating the original row,
  which keeps the table strictly append-only.)
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    event,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, Mapper, mapped_column, relationship

from app.db import Base


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC (portable across SQLite/Postgres), always returns aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: pass an aware UTC datetime")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


def utcnow() -> datetime:
    return datetime.now(UTC)


class EntryType(enum.StrEnum):
    credit_sale = "credit_sale"
    cash_sale = "cash_sale"
    payment_received = "payment_received"
    adjustment = "adjustment"


class VoiceStatus(enum.StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"
    failed = "failed"


class Shop(Base):
    __tablename__ = "shop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_phone: Mapped[str] = mapped_column(String(20), unique=True)
    pin_hash: Mapped[str] = mapped_column(String(255))
    default_language: Mapped[str] = mapped_column(String(10), default="hi")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Customer(Base):
    __tablename__ = "customer"
    __table_args__ = (UniqueConstraint("shop_id", "display_name", name="uq_customer_shop_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shop.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    phone: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class VoiceEvent(Base):
    """One voice turn: the debug trail and the demo metrics (latency per stage)."""

    __tablename__ = "voice_event"
    __table_args__ = (
        UniqueConstraint("shop_id", "idempotency_key", name="uq_voice_event_idem"),
        Index("ix_voice_event_shop_created", "shop_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shop.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    audio_path: Mapped[str | None] = mapped_column(String(255))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str | None] = mapped_column(Text)
    stt_model: Mapped[str | None] = mapped_column(String(40))
    stt_request_id: Mapped[str | None] = mapped_column(String(64))
    detected_lang: Mapped[str | None] = mapped_column(String(12))
    nlu_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    nlu_source: Mapped[str | None] = mapped_column(String(10))
    confidence: Mapped[float | None] = mapped_column(Float)  # model confidence, not money
    status: Mapped[VoiceStatus] = mapped_column(
        Enum(VoiceStatus, native_enum=False, length=12), default=VoiceStatus.pending
    )
    latency_stt_ms: Mapped[int | None] = mapped_column(Integer)
    latency_nlu_ms: Mapped[int | None] = mapped_column(Integer)
    latency_tts_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class LedgerEntry(Base):
    __tablename__ = "ledger_entry"
    __table_args__ = (
        # Originals are positive; reversals carry the negated amount; adjustments are signed.
        CheckConstraint(
            "(reverses_entry_id IS NULL AND (amount_paise > 0 OR "
            "(type = 'adjustment' AND amount_paise <> 0))) OR "
            "(reverses_entry_id IS NOT NULL AND amount_paise <> 0)",
            name="ck_ledger_entry_amount_sign",
        ),
        CheckConstraint(
            "type IN ('cash_sale', 'adjustment') OR customer_id IS NOT NULL",
            name="ck_ledger_entry_customer_required",
        ),
        UniqueConstraint("reverses_entry_id", name="uq_ledger_entry_one_reversal"),
        Index("ix_ledger_entry_shop_created", "shop_id", "created_at"),
        Index("ix_ledger_entry_customer", "customer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shop.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customer.id"))
    voice_event_id: Mapped[int | None] = mapped_column(ForeignKey("voice_event.id"))
    type: Mapped[EntryType] = mapped_column(Enum(EntryType, native_enum=False, length=20))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(200))
    reverses_entry_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entry.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    lines: Mapped[list[LedgerLine]] = relationship(
        back_populates="entry", lazy="selectin", order_by="LedgerLine.id"
    )
    customer: Mapped[Customer | None] = relationship(lazy="joined")

    @property
    def is_reversal(self) -> bool:
        return self.reverses_entry_id is not None


class LedgerLine(Base):
    __tablename__ = "ledger_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("ledger_entry.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(60))
    qty: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    amount_paise: Mapped[int | None] = mapped_column(BigInteger)

    entry: Mapped[LedgerEntry] = relationship(back_populates="lines")


class AppendOnlyViolationError(Exception):
    """Raised on any attempt to UPDATE or DELETE a ledger row through the ORM."""


def _forbid(action: str) -> Any:
    def listener(mapper: Mapper[Any], connection: Any, target: Any) -> None:
        raise AppendOnlyViolationError(
            f"{type(target).__name__} is append-only: {action} is not allowed; post a reversal"
        )

    return listener


for _model in (LedgerEntry, LedgerLine):
    event.listen(_model, "before_update", _forbid("UPDATE"))
    event.listen(_model, "before_delete", _forbid("DELETE"))
