"""Hypothesis property tests (qa-voice-testing skill): balances always reconcile with an
independent Python model, reversals net to zero, money is always int, rows only ever grow."""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ledger import queries as q
from app.ledger import service as svc
from app.ledger.models import EntryType, LedgerEntry
from tests.ledger.conftest import new_shop

amounts = st.integers(min_value=1, max_value=10_00_000_00)
op = st.one_of(
    st.tuples(st.just("credit"), st.integers(0, 2), amounts),
    st.tuples(st.just("pay"), st.integers(0, 2), amounts),
    st.tuples(st.just("cash"), st.just(0), amounts),
    st.tuples(st.just("adjust"), st.integers(0, 2), amounts, st.booleans()),
    st.tuples(st.just("reverse"), st.integers(0, 50)),
    st.tuples(
        st.just("undo"),
    ),
)
SIGN = {EntryType.credit_sale: 1, EntryType.payment_received: -1, EntryType.adjustment: 1}
DB_SETTINGS = settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@DB_SETTINGS
@given(ops=st.lists(op, max_size=25))
def test_balances_reconcile_with_model(db: Session, ops: list[tuple[object, ...]]) -> None:
    shop = new_shop(db)
    custs = [svc.create_customer(db, shop_id=shop.id, display_name=f"C{i}").id for i in range(3)]
    db.commit()
    live: list[LedgerEntry] = []  # entries that can still be reversed, oldest first
    model = dict.fromkeys(custs, 0)
    rows_seen = 0

    def book(e: LedgerEntry) -> None:
        if e.customer_id is not None:
            model[e.customer_id] += SIGN.get(e.type, 0) * e.amount_paise

    for o in ops:
        kind = o[0]
        try:
            if kind in ("credit", "pay", "cash"):
                t = {"credit": EntryType.credit_sale, "pay": EntryType.payment_received,
                     "cash": EntryType.cash_sale}[kind]  # type: ignore[index]  # fmt: skip
                cid = custs[o[1]] if kind != "cash" else None  # type: ignore[index]
                e = svc.record_entry(db, shop_id=shop.id, type=t, amount_paise=o[2],  # type: ignore[arg-type]
                                     customer_id=cid)  # fmt: skip
                live.append(e)
                book(e)
            elif kind == "adjust":
                amt = o[2] if o[3] else -o[2]  # type: ignore[operator]
                e = svc.record_adjustment(db, shop_id=shop.id, customer_id=custs[o[1]],  # type: ignore[index]
                                          amount_paise=amt, note="adj")  # type: ignore[arg-type]  # fmt: skip
                live.append(e)
                book(e)
            elif kind == "reverse" and live:
                target = live.pop(o[1] % len(live))  # type: ignore[operator]
                book(svc.reverse_entry(db, shop_id=shop.id, entry_id=target.id))
            elif kind == "undo" and live:
                r = svc.undo_last(db, shop_id=shop.id)
                live = [e for e in live if e.id != r.reverses_entry_id]
                book(r)
            db.commit()
        except svc.LedgerError:
            db.rollback()
        rows = db.scalar(select(func.count()).where(LedgerEntry.shop_id == shop.id)) or 0
        assert rows >= rows_seen  # append-only: the row count never shrinks
        rows_seen = rows

    for cid in custs:
        bal = q.customer_balance(db, shop.id, cid)
        assert type(bal) is int
        assert bal == model[cid]
    assert sum(b.balance_paise for b in q.balances(db, shop.id)) == sum(model.values())


@DB_SETTINGS
@given(amount=amounts, kind=st.sampled_from([EntryType.credit_sale, EntryType.payment_received]))
def test_any_entry_plus_its_reversal_is_zero(db: Session, amount: int, kind: EntryType) -> None:
    shop = new_shop(db)
    c = svc.create_customer(db, shop_id=shop.id, display_name="X")
    e = svc.record_entry(db, shop_id=shop.id, type=kind, amount_paise=amount, customer_id=c.id)
    svc.reverse_entry(db, shop_id=shop.id, entry_id=e.id)
    db.commit()
    assert q.customer_balance(db, shop.id, c.id) == 0
    assert q.sales_summary(db, shop.id).entries == 0
