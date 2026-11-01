"""Read side. Balances are computed in SQL from the append-only rows, never stored.

balance(customer) = SUM(credit_sale) - SUM(payment_received) + SUM(adjustment)
Reversal rows carry the negated amount with the original's type, so they net out automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import BigInteger, case, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.ledger.models import Customer, EntryType, LedgerEntry, utcnow

SALE_TYPES = (EntryType.credit_sale, EntryType.cash_sale)


def signed_amount() -> ColumnElement[int]:
    return case(
        (LedgerEntry.type == EntryType.credit_sale, LedgerEntry.amount_paise),
        (LedgerEntry.type == EntryType.payment_received, -LedgerEntry.amount_paise),
        (LedgerEntry.type == EntryType.adjustment, LedgerEntry.amount_paise),
        else_=0,
    )


def _int_sum(expr: ColumnElement[int]) -> ColumnElement[int]:
    # Postgres SUM(bigint) returns NUMERIC (-> Decimal); cast keeps it an exact int everywhere.
    return cast(func.coalesce(func.sum(expr), 0), BigInteger)


def customer_balance(db: Session, shop_id: int, customer_id: int) -> int:
    stmt = select(_int_sum(signed_amount())).where(
        LedgerEntry.shop_id == shop_id, LedgerEntry.customer_id == customer_id
    )
    return int(db.scalar(stmt) or 0)


@dataclass(frozen=True)
class CustomerBalance:
    customer_id: int
    display_name: str
    aliases: list[str]
    phone: str | None
    balance_paise: int
    last_activity: datetime | None


def balances(db: Session, shop_id: int) -> list[CustomerBalance]:
    """Every customer of the shop with their balance (zero if no entries), name order."""
    agg = (
        select(
            LedgerEntry.customer_id.label("cid"),
            _int_sum(signed_amount()).label("bal"),
            func.max(LedgerEntry.created_at).label("last"),
        )
        .where(LedgerEntry.shop_id == shop_id, LedgerEntry.customer_id.is_not(None))
        .group_by(LedgerEntry.customer_id)
        .subquery()
    )
    rows = db.execute(
        select(Customer, agg.c.bal, agg.c.last)
        .outerjoin(agg, agg.c.cid == Customer.id)
        .where(Customer.shop_id == shop_id)
        .order_by(Customer.display_name)
    ).all()
    out = []
    for customer, bal, last in rows:
        if last is not None and last.tzinfo is None:  # raw aggregate bypasses the TypeDecorator
            last = last.replace(tzinfo=ZoneInfo("UTC"))
        out.append(
            CustomerBalance(
                customer.id,
                customer.display_name,
                list(customer.aliases),
                customer.phone,
                int(bal or 0),
                last,
            )
        )
    return out


def dues(db: Session, shop_id: int, limit: int = 5) -> list[CustomerBalance]:
    """Who owes the most (balance > 0), highest first."""
    owing = [b for b in balances(db, shop_id) if b.balance_paise > 0]
    return sorted(owing, key=lambda b: (-b.balance_paise, b.display_name))[:limit]


def day_bounds_utc(now: datetime, tz: str = "Asia/Kolkata") -> tuple[datetime, datetime]:
    """'aaj' means the shop's local day (IST), not UTC."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    return start.astimezone(ZoneInfo("UTC")), (start + timedelta(days=1)).astimezone(
        ZoneInfo("UTC")
    )


@dataclass(frozen=True)
class SalesSummary:
    total_paise: int  # cash + credit sales, net of cancellations made today
    cash_paise: int
    credit_paise: int
    payments_paise: int
    entries: int  # live (not cancelled) sale entries today


def sales_summary(
    db: Session, shop_id: int, now: datetime | None = None, tz: str = "Asia/Kolkata"
) -> SalesSummary:
    start, end = day_bounds_utc(now or utcnow(), tz)
    today = (
        LedgerEntry.shop_id == shop_id,
        LedgerEntry.created_at >= start,
        LedgerEntry.created_at < end,
    )

    def total(t: EntryType) -> ColumnElement[int]:
        return _int_sum(case((LedgerEntry.type == t, LedgerEntry.amount_paise), else_=0))

    cash, credit, paid = db.execute(
        select(
            total(EntryType.cash_sale),
            total(EntryType.credit_sale),
            total(EntryType.payment_received),
        ).where(*today)
    ).one()
    rev = LedgerEntry.__table__.alias("rev")
    live = db.scalar(
        select(func.count(LedgerEntry.id)).where(
            *today,
            LedgerEntry.type.in_(SALE_TYPES),
            LedgerEntry.reverses_entry_id.is_(None),
            ~select(rev.c.id).where(rev.c.reverses_entry_id == LedgerEntry.id).exists(),
        )
    )
    return SalesSummary(int(cash) + int(credit), int(cash), int(credit), int(paid), int(live or 0))


def entries(
    db: Session,
    shop_id: int,
    *,
    customer_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
) -> list[LedgerEntry]:
    stmt = select(LedgerEntry).where(LedgerEntry.shop_id == shop_id)
    if customer_id is not None:
        stmt = stmt.where(LedgerEntry.customer_id == customer_id)
    if since is not None:
        stmt = stmt.where(LedgerEntry.created_at >= since)
    if until is not None:
        stmt = stmt.where(LedgerEntry.created_at < until)
    stmt = stmt.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc()).limit(
        min(limit, 500)
    )
    return list(db.scalars(stmt).unique())


def reversed_by(db: Session, entry_ids: list[int]) -> dict[int, int]:
    """original entry id -> id of the reversal that cancelled it (the spec's `reversed_by`)."""
    if not entry_ids:
        return {}
    rows = db.execute(
        select(LedgerEntry.reverses_entry_id, LedgerEntry.id).where(
            LedgerEntry.reverses_entry_id.in_(entry_ids)
        )
    ).all()
    return {int(orig): int(rev) for orig, rev in rows if orig is not None}


def format_inr(paise: int) -> str:
    """12000000 -> '₹1,20,000'; 1250 -> '₹12.50'; -500 -> '-₹5'. Integer maths, Indian grouping."""
    sign = "-" if paise < 0 else ""
    rupees, p = divmod(abs(paise), 100)
    s = str(rupees)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join([*groups, tail])
    return f"{sign}₹{s}" + (f".{p:02d}" if p else "")
