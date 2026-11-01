"""Idempotent demo data: one shop + a few customers with a realistic udhaar history.

    make seed            (uses DATABASE_URL; run `make migrate` first)

Login: phone 9999999999, PIN from SEED_PIN (default 1234, dev only). Change it with
`make set-pin PHONE=9999999999 PIN=4821` before any real use.
"""

from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_pin
from app.db import get_engine
from app.ledger import service as svc
from app.ledger.models import EntryType, Shop

CUSTOMERS: list[tuple[str, list[str]]] = [
    ("Ramesh Sharma", ["Sharma ji", "Ramesh bhai"]),
    ("Suresh Sharma", ["Suresh ji"]),
    ("Anil Gupta", ["Gupta ji"]),
    ("Vikas Verma", ["Verma ji"]),
    ("Meena", ["Meena didi"]),
    ("Patil Kaka", ["Patil"]),
]
HISTORY: list[tuple[str, EntryType, int]] = [
    ("Ramesh Sharma", EntryType.credit_sale, 45000),
    ("Anil Gupta", EntryType.credit_sale, 62000),
    ("Anil Gupta", EntryType.payment_received, 30000),
    ("Vikas Verma", EntryType.credit_sale, 12000),
    ("Meena", EntryType.credit_sale, 8000),
    ("Patil Kaka", EntryType.credit_sale, 20000),
]


def seed(db: Session) -> str:
    if db.scalar(select(Shop.id).limit(1)) is not None:
        return "already seeded - nothing to do"
    pin = os.environ.get("SEED_PIN") or ("1234" if get_settings().app_env != "prod" else "")
    if not pin:
        raise SystemExit("Set SEED_PIN (4 digits) to seed a prod shop")
    shop = svc.create_shop(
        db, name="Ramesh Kirana Store", owner_phone="9999999999", pin_hash=hash_pin(pin)
    )
    ids = {}
    for name, aliases in CUSTOMERS:
        ids[name] = svc.create_customer(db, shop_id=shop.id, display_name=name, aliases=aliases).id
    for name, kind, paise in HISTORY:
        svc.record_entry(
            db,
            shop_id=shop.id,
            type=kind,
            amount_paise=paise,
            customer_id=ids[name],
            note="demo seed",
        )
    db.commit()
    return f"seeded shop {shop.id} with {len(CUSTOMERS)} customers and {len(HISTORY)} entries"


if __name__ == "__main__":
    with Session(get_engine()) as session:
        print(seed(session))
