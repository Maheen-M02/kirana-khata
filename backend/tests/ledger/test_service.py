from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.ledger import queries as q
from app.ledger import service as svc
from app.ledger.models import AppendOnlyViolationError, EntryType, LedgerEntry, Shop
from tests.ledger.conftest import new_shop

C, P, CASH = EntryType.credit_sale, EntryType.payment_received, EntryType.cash_sale


def credit(db: Session, shop: Shop, cid: int, paise: int) -> LedgerEntry:
    e = svc.record_entry(db, shop_id=shop.id, type=C, amount_paise=paise, customer_id=cid)
    db.commit()
    return e


def test_credit_then_payment_balance(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="Ramesh Sharma")
    credit(db, shop, c.id, 12000)
    credit(db, shop, c.id, 8000)
    svc.record_entry(db, shop_id=shop.id, type=P, amount_paise=5000, customer_id=c.id)
    svc.record_entry(db, shop_id=shop.id, type=CASH, amount_paise=9999)  # no customer effect
    db.commit()
    assert q.customer_balance(db, shop.id, c.id) == 15000
    assert isinstance(q.customer_balance(db, shop.id, c.id), int)


def test_reversal_nets_to_zero_and_keeps_original(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="Gupta ji")
    e = credit(db, shop, c.id, 30000)
    r = svc.reverse_entry(db, shop_id=shop.id, entry_id=e.id)
    db.commit()
    assert q.customer_balance(db, shop.id, c.id) == 0
    assert (r.type, r.amount_paise, r.reverses_entry_id) == (C, -30000, e.id)
    assert db.get(LedgerEntry, e.id).amount_paise == 30000  # original untouched
    assert q.reversed_by(db, [e.id]) == {e.id: r.id}


def test_cannot_reverse_twice_or_reverse_a_reversal(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="Verma ji")
    e = credit(db, shop, c.id, 1000)
    r = svc.reverse_entry(db, shop_id=shop.id, entry_id=e.id)
    db.commit()
    with pytest.raises(svc.LedgerError) as ei:
        svc.reverse_entry(db, shop_id=shop.id, entry_id=e.id)
    assert ei.value.code == "already_reversed"
    with pytest.raises(svc.LedgerError) as ei:
        svc.reverse_entry(db, shop_id=shop.id, entry_id=r.id)
    assert ei.value.code == "cannot_reverse_reversal"


def test_undo_last_walks_back_through_live_entries(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="Khan sahab")
    a, b = credit(db, shop, c.id, 100), credit(db, shop, c.id, 200)
    r1 = svc.undo_last(db, shop_id=shop.id)
    db.commit()
    r2 = svc.undo_last(db, shop_id=shop.id)
    db.commit()
    assert (r1.reverses_entry_id, r2.reverses_entry_id) == (b.id, a.id)
    assert q.customer_balance(db, shop.id, c.id) == 0
    with pytest.raises(svc.LedgerError) as ei:
        svc.undo_last(db, shop_id=shop.id)
    assert ei.value.code == "nothing_to_undo"


@pytest.mark.parametrize("bad", [12.5, 0, -100, True, Decimal("12"), "120", 10**12])
def test_money_must_be_positive_int_paise(db: Session, shop: Shop, bad: object) -> None:
    with pytest.raises(svc.LedgerError):
        svc.record_entry(db, shop_id=shop.id, type=CASH, amount_paise=bad)  # type: ignore[arg-type]


def test_credit_and_payment_need_a_customer(db: Session, shop: Shop) -> None:
    for t in (C, P):
        with pytest.raises(svc.LedgerError) as ei:
            svc.record_entry(db, shop_id=shop.id, type=t, amount_paise=100)
        assert ei.value.code == "customer_required"


def test_shops_are_isolated(db: Session, shop: Shop) -> None:
    other = new_shop(db)
    theirs = svc.create_customer(db, shop_id=other.id, display_name="Sharma ji")
    e = credit(db, other, theirs.id, 5000)
    with pytest.raises(svc.LedgerError) as ei:  # can't book against another shop's customer
        svc.record_entry(db, shop_id=shop.id, type=C, amount_paise=100, customer_id=theirs.id)
    assert ei.value.status_code == 404
    with pytest.raises(svc.LedgerError):  # nor cancel another shop's entry
        svc.reverse_entry(db, shop_id=shop.id, entry_id=e.id)
    assert q.balances(db, shop.id) == []
    assert q.sales_summary(db, shop.id).total_paise == 0


def test_lines_and_adjustments(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="Meena didi")
    e = svc.record_entry(db, shop_id=shop.id, type=C, amount_paise=12000, customer_id=c.id,
                         lines=[svc.LineIn("Cheeni", Decimal("2"), "kilo"),
                                svc.LineIn("Parle-G", Decimal("1"))])  # fmt: skip
    svc.record_adjustment(db, shop_id=shop.id, customer_id=c.id, amount_paise=-2000,
                          note="purana khata")  # fmt: skip
    db.commit()
    db.expire_all()
    assert [(ln.item_name, ln.qty, ln.unit) for ln in db.get(LedgerEntry, e.id).lines] == [
        ("cheeni", Decimal("2.000"), "kilo"), ("parle-g", Decimal("1.000"), None)
    ]  # fmt: skip
    assert q.customer_balance(db, shop.id, c.id) == 10000


def test_orm_update_and_delete_are_refused(db: Session, shop: Shop) -> None:
    e = svc.record_entry(db, shop_id=shop.id, type=CASH, amount_paise=500)
    db.commit()
    e.amount_paise = 1
    with pytest.raises(AppendOnlyViolationError):
        db.flush()
    db.rollback()
    db.delete(db.get(LedgerEntry, e.id))
    with pytest.raises(AppendOnlyViolationError):
        db.flush()
    db.rollback()


@pytest.mark.parametrize(
    "sql",
    ["UPDATE ledger_entry SET amount_paise = 1 WHERE id = :id",
     "DELETE FROM ledger_entry WHERE id = :id"],
)  # fmt: skip
def test_raw_sql_update_and_delete_hit_db_triggers(db: Session, shop: Shop, sql: str) -> None:
    e = svc.record_entry(db, shop_id=shop.id, type=CASH, amount_paise=500)
    db.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text(sql), {"id": e.id})
    db.rollback()
    assert db.get(LedgerEntry, e.id).amount_paise == 500


@pytest.mark.parametrize(
    ("type_", "amount", "customer"),
    [("credit_sale", 100, None), ("cash_sale", 0, None), ("cash_sale", -5, None)],
)
def test_db_check_constraints(
    db: Session, shop: Shop, type_: str, amount: int, customer: None
) -> None:
    with pytest.raises(DBAPIError):
        db.execute(
            text(
                "INSERT INTO ledger_entry (shop_id, customer_id, type, amount_paise, created_at) "
                "VALUES (:s, :c, :t, :a, CURRENT_TIMESTAMP)"
            ),
            {"s": shop.id, "c": customer, "t": type_, "a": amount},
        )
    db.rollback()


def test_customer_rules(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="  Ramesh   Sharma ",
                            aliases=["Sharma ji", "Ramesh Sharma"])  # fmt: skip
    assert c.display_name == "Ramesh Sharma"
    assert c.aliases == ["Sharma ji"]
    with pytest.raises(svc.LedgerError) as ei:
        svc.create_customer(db, shop_id=shop.id, display_name="Ramesh Sharma")
    assert ei.value.status_code == 409
    assert svc.add_alias(db, c, "Sharma uncle")
    assert not svc.add_alias(db, c, "Sharma ji")
    db.commit()
    db.expire_all()
    assert svc.get_customer(db, shop.id, c.id).aliases == ["Sharma ji", "Sharma uncle"]


def test_sales_today_uses_ist_day(db: Session, shop: Shop) -> None:
    def at(ts: datetime, paise: int) -> None:
        db.add(LedgerEntry(shop_id=shop.id, type=CASH, amount_paise=paise, created_at=ts))

    at(datetime(2026, 11, 1, 18, 29, tzinfo=UTC), 100)  # 23:59 IST, 1 Nov
    at(datetime(2026, 11, 1, 18, 31, tzinfo=UTC), 200)  # 00:01 IST, 2 Nov
    at(datetime(2026, 11, 2, 18, 0, tzinfo=UTC), 400)  # 23:30 IST, 2 Nov
    db.commit()
    s = q.sales_summary(db, shop.id, now=datetime(2026, 11, 2, 6, 0, tzinfo=UTC))
    assert (s.total_paise, s.cash_paise, s.entries) == (600, 600, 2)


def test_sales_summary_counts_live_entries_and_nets_cancellations(db: Session, shop: Shop) -> None:
    c = svc.create_customer(db, shop_id=shop.id, display_name="Joshi ji")
    credit(db, shop, c.id, 25000)
    cash = svc.record_entry(db, shop_id=shop.id, type=CASH, amount_paise=5000)
    svc.record_entry(db, shop_id=shop.id, type=P, amount_paise=10000, customer_id=c.id)
    svc.reverse_entry(db, shop_id=shop.id, entry_id=cash.id)
    db.commit()
    s = q.sales_summary(db, shop.id)
    assert (s.total_paise, s.credit_paise, s.cash_paise, s.payments_paise, s.entries) == (
        25000, 25000, 0, 10000, 1
    )  # fmt: skip


def test_dues_and_balances(db: Session, shop: Shop) -> None:
    a = svc.create_customer(db, shop_id=shop.id, display_name="A")
    b = svc.create_customer(db, shop_id=shop.id, display_name="B")
    zero = svc.create_customer(db, shop_id=shop.id, display_name="Z")
    credit(db, shop, a.id, 100)
    credit(db, shop, b.id, 900)
    svc.record_entry(db, shop_id=shop.id, type=P, amount_paise=200, customer_id=a.id)  # advance
    db.commit()
    bals = {x.display_name: x.balance_paise for x in q.balances(db, shop.id)}
    assert bals == {"A": -100, "B": 900, "Z": 0}
    assert [d.display_name for d in q.dues(db, shop.id)] == ["B"]
    assert (
        next(x for x in q.balances(db, shop.id) if x.customer_id == zero.id).last_activity is None
    )


@pytest.mark.parametrize(
    ("paise", "text_"),
    [(12000000, "₹1,20,000"), (1250, "₹12.50"), (-500, "-₹5"), (100, "₹1"), (0, "₹0"),
     (99999999, "₹9,99,999.99"), (123456789012, "₹1,23,45,67,890.12")],
)  # fmt: skip
def test_format_inr(paise: int, text_: str) -> None:
    assert q.format_inr(paise) == text_
