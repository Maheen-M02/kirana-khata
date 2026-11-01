"""Ledger writes. Small functions; the caller owns the transaction (commit/rollback).

Nothing here is reachable from the voice path without an explicit "haan" (Phase 4 enforces it):
these functions only *record* what was already confirmed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.ledger.models import Customer, EntryType, LedgerEntry, LedgerLine, Shop, utcnow
from app.nlu.schema import MAX_AMOUNT_PAISE


class LedgerError(AppError):
    """Expected business failure with a short Hinglish message for the shopkeeper."""


@dataclass(frozen=True)
class LineIn:
    item_name: str
    qty: Decimal | None = None
    unit: str | None = None
    amount_paise: int | None = None


def check_amount(amount_paise: object, *, allow_negative: bool = False) -> int:
    """Money must be a plain int of paise. bool, float, Decimal and str are all refused."""
    if type(amount_paise) is not int:
        raise LedgerError("bad_amount", "Rakam sahi nahi hai.")
    if amount_paise == 0 or (amount_paise < 0 and not allow_negative):
        raise LedgerError("bad_amount", "Rakam sahi nahi hai.")
    if abs(amount_paise) > MAX_AMOUNT_PAISE:
        raise LedgerError("amount_too_large", "Itni badi rakam nahi likh sakte.")
    return amount_paise


# ------------------------------------------------------------------ shop / customers
def create_shop(
    db: Session, *, name: str, owner_phone: str, pin_hash: str, default_language: str = "hi"
) -> Shop:
    shop = Shop(
        name=name, owner_phone=owner_phone, pin_hash=pin_hash, default_language=default_language
    )
    db.add(shop)
    db.flush()
    return shop


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 80:
        raise LedgerError("bad_name", "Naam sahi nahi hai.")
    return cleaned


def create_customer(
    db: Session,
    *,
    shop_id: int,
    display_name: str,
    phone: str | None = None,
    aliases: Sequence[str] = (),
) -> Customer:
    name = _clean_name(display_name)
    clash = db.scalar(
        select(Customer.id).where(Customer.shop_id == shop_id, Customer.display_name == name)
    )
    if clash is not None:
        raise LedgerError("customer_exists", f"'{name}' pehle se hai.", 409)
    customer = Customer(
        shop_id=shop_id,
        display_name=name,
        phone=phone,
        aliases=sorted({_clean_name(a) for a in aliases if a.strip()} - {name}),
    )
    db.add(customer)
    db.flush()
    return customer


def get_customer(db: Session, shop_id: int, customer_id: int) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.shop_id != shop_id:  # never leak another shop's data
        raise LedgerError("customer_not_found", "Yeh customer nahi mila.", 404)
    return customer


def add_alias(db: Session, customer: Customer, alias: str) -> bool:
    """Learn a spoken variant ("Sharma uncle"). Customers are mutable; ledger rows are not."""
    a = _clean_name(alias)
    if a == customer.display_name or a in customer.aliases:
        return False
    customer.aliases = sorted({*customer.aliases, a})  # reassign so JSON change is tracked
    db.flush()
    return True


# ------------------------------------------------------------------ entries
def record_entry(
    db: Session,
    *,
    shop_id: int,
    type: EntryType,
    amount_paise: int,
    customer_id: int | None = None,
    voice_event_id: int | None = None,
    note: str | None = None,
    lines: Sequence[LineIn] = (),
) -> LedgerEntry:
    amount = check_amount(amount_paise)
    if type == EntryType.adjustment:
        raise LedgerError("use_adjustment", "Adjustment alag se likhiye.")
    if type in (EntryType.credit_sale, EntryType.payment_received) and customer_id is None:
        raise LedgerError("customer_required", "Kis customer ka hai, yeh batana zaroori hai.")
    if customer_id is not None:
        get_customer(db, shop_id, customer_id)
    entry = LedgerEntry(
        shop_id=shop_id,
        customer_id=customer_id,
        voice_event_id=voice_event_id,
        type=type,
        amount_paise=amount,
        note=(note or None) and note[:200],
        created_at=utcnow(),
    )
    db.add(entry)
    db.flush()
    for line in lines:
        if line.amount_paise is not None:
            check_amount(line.amount_paise)
        db.add(
            LedgerLine(
                entry_id=entry.id,
                item_name=line.item_name.strip().lower()[:60],
                qty=line.qty,
                unit=line.unit,
                amount_paise=line.amount_paise,
            )
        )
    db.flush()
    return entry


def record_adjustment(
    db: Session, *, shop_id: int, customer_id: int | None, amount_paise: int, note: str
) -> LedgerEntry:
    """Signed correction outside the voice flow (e.g. opening balance from the old khata)."""
    amount = check_amount(amount_paise, allow_negative=True)
    if customer_id is not None:
        get_customer(db, shop_id, customer_id)
    entry = LedgerEntry(
        shop_id=shop_id,
        customer_id=customer_id,
        type=EntryType.adjustment,
        amount_paise=amount,
        note=note[:200],
        created_at=utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry


def is_reversed(db: Session, entry_id: int) -> bool:
    return bool(db.scalar(select(exists().where(LedgerEntry.reverses_entry_id == entry_id))))


def reverse_entry(
    db: Session,
    *,
    shop_id: int,
    entry_id: int,
    note: str | None = None,
    voice_event_id: int | None = None,
) -> LedgerEntry:
    """Append the mirror entry. The original row is never touched."""
    original = db.get(LedgerEntry, entry_id)
    if original is None or original.shop_id != shop_id:
        raise LedgerError("entry_not_found", "Yeh entry nahi mili.", 404)
    if original.is_reversal:
        raise LedgerError("cannot_reverse_reversal", "Cancel ko cancel nahi kar sakte.", 409)
    if is_reversed(db, entry_id):
        raise LedgerError("already_reversed", "Yeh entry pehle hi cancel ho chuki hai.", 409)
    reversal = LedgerEntry(
        shop_id=shop_id,
        customer_id=original.customer_id,
        voice_event_id=voice_event_id,
        type=original.type,
        amount_paise=-original.amount_paise,
        note=(note or "cancel")[:200],
        reverses_entry_id=original.id,
        created_at=utcnow(),
    )
    db.add(reversal)
    try:
        db.flush()
    except IntegrityError as e:  # concurrent double-undo hits uq_ledger_entry_one_reversal
        db.rollback()
        raise LedgerError("already_reversed", "Yeh entry pehle hi cancel ho chuki hai.", 409) from e
    return reversal


def last_reversible_entry(db: Session, shop_id: int) -> LedgerEntry | None:
    reversal = LedgerEntry.__table__.alias("rev")
    stmt = (
        select(LedgerEntry)
        .where(
            LedgerEntry.shop_id == shop_id,
            LedgerEntry.reverses_entry_id.is_(None),
            ~exists().where(reversal.c.reverses_entry_id == LedgerEntry.id),
        )
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def undo_last(db: Session, *, shop_id: int, voice_event_id: int | None = None) -> LedgerEntry:
    """Reverse the newest live entry. Returns the reversal."""
    target = last_reversible_entry(db, shop_id)
    if target is None:
        raise LedgerError("nothing_to_undo", "Cancel karne ke liye koi entry nahi hai.", 409)
    return reverse_entry(
        db, shop_id=shop_id, entry_id=target.id, note="undo", voice_event_id=voice_event_id
    )
