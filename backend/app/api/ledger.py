"""Ledger, customers and reports REST API. Every query is scoped by the current shop."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, status

from app.api.schemas import (
    AliasIn,
    CustomerDetail,
    CustomerIn,
    CustomerOut,
    DuesOut,
    EntryIn,
    EntryOut,
    SalesOut,
    UndoOut,
)
from app.config import get_settings
from app.deps import DbSession, ShopId
from app.ledger import queries
from app.ledger import service as svc
from app.ledger.models import EntryType, LedgerEntry, utcnow
from app.ledger.queries import format_inr
from app.nlu.templates import UNDO_DONE, dues_list_text, sales_today_text

router = APIRouter(tags=["ledger"])


def _entries_out(db: DbSession, items: list[LedgerEntry]) -> list[EntryOut]:
    rev = queries.reversed_by(db, [e.id for e in items])
    return [EntryOut.of(e, rev) for e in items]


def _customer_out(db: DbSession, shop_id: int, customer_id: int) -> CustomerOut:
    b = next(b for b in queries.balances(db, shop_id) if b.customer_id == customer_id)
    return CustomerOut.of(b)


# ------------------------------------------------------------------ customers
@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: DbSession, shop_id: ShopId) -> list[CustomerOut]:
    return [CustomerOut.of(b) for b in queries.balances(db, shop_id)]


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(body: CustomerIn, db: DbSession, shop_id: ShopId) -> CustomerOut:
    c = svc.create_customer(
        db, shop_id=shop_id, display_name=body.display_name, phone=body.phone, aliases=body.aliases
    )
    db.commit()
    return _customer_out(db, shop_id, c.id)


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def customer_detail(
    customer_id: int, db: DbSession, shop_id: ShopId, limit: int = Query(100, le=500)
) -> CustomerDetail:
    svc.get_customer(db, shop_id, customer_id)
    base = _customer_out(db, shop_id, customer_id)
    items = queries.entries(db, shop_id, customer_id=customer_id, limit=limit)
    return CustomerDetail(**base.model_dump(), entries=_entries_out(db, items))


@router.post("/customers/{customer_id}/aliases", response_model=CustomerOut)
def add_alias(customer_id: int, body: AliasIn, db: DbSession, shop_id: ShopId) -> CustomerOut:
    svc.add_alias(db, svc.get_customer(db, shop_id, customer_id), body.alias)
    db.commit()
    return _customer_out(db, shop_id, customer_id)


# ------------------------------------------------------------------ entries
@router.get("/ledger/entries", response_model=list[EntryOut])
def list_entries(
    db: DbSession,
    shop_id: ShopId,
    day: Literal["today", "all"] = "today",
    customer_id: int | None = None,
    limit: int = Query(100, le=500),
) -> list[EntryOut]:
    since = until = None
    if day == "today":
        since, until = queries.day_bounds_utc(utcnow(), get_settings().tz)
    items = queries.entries(
        db, shop_id, customer_id=customer_id, since=since, until=until, limit=limit
    )
    return _entries_out(db, items)


@router.post("/ledger/entries", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(body: EntryIn, db: DbSession, shop_id: ShopId) -> EntryOut:
    entry = svc.record_entry(
        db,
        shop_id=shop_id,
        type=EntryType(body.type),
        amount_paise=body.amount_paise,
        customer_id=body.customer_id,
        note=body.note,
        lines=[svc.LineIn(ln.item_name, ln.qty, ln.unit, ln.amount_paise) for ln in body.lines],
    )
    db.commit()
    return EntryOut.of(entry, {})


@router.post("/ledger/entries/{entry_id}/reverse", response_model=EntryOut)
def reverse_entry(entry_id: int, db: DbSession, shop_id: ShopId) -> EntryOut:
    reversal = svc.reverse_entry(db, shop_id=shop_id, entry_id=entry_id)
    db.commit()
    return EntryOut.of(reversal, {})


@router.post("/ledger/undo", response_model=UndoOut)
def undo_last(db: DbSession, shop_id: ShopId) -> UndoOut:
    reversal = svc.undo_last(db, shop_id=shop_id)
    db.commit()
    assert reversal.reverses_entry_id is not None
    return UndoOut(
        reversal=EntryOut.of(reversal, {}), original_id=reversal.reverses_entry_id, speak=UNDO_DONE
    )


# ------------------------------------------------------------------ reports
@router.get("/reports/today", response_model=SalesOut)
def sales_today(db: DbSession, shop_id: ShopId) -> SalesOut:
    s = queries.sales_summary(db, shop_id, tz=get_settings().tz)
    return SalesOut.of(
        s, sales_today_text(s.total_paise, s.entries, s.credit_paise, s.payments_paise)
    )


@router.get("/reports/dues", response_model=DuesOut)
def dues(db: DbSession, shop_id: ShopId, limit: int = Query(5, ge=1, le=100)) -> DuesOut:
    owing = queries.dues(db, shop_id, limit=limit)
    total = sum(b.balance_paise for b in owing)
    return DuesOut(
        customers=[CustomerOut.of(b) for b in owing],
        total_paise=total,
        total_display=format_inr(total),
        speak=dues_list_text([(b.display_name, b.balance_paise) for b in owing]),
    )
