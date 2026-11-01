"""Set/rotate the shop owner's 4-digit PIN.   make set-pin PHONE=9999999999 PIN=4821"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_pin, normalise_phone
from app.db import get_engine
from app.ledger.models import Shop


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m scripts.set_pin PHONE PIN")
        return 2
    phone, pin = normalise_phone(argv[0]), argv[1]
    with Session(get_engine()) as db:
        shop = db.scalar(select(Shop).where(Shop.owner_phone == phone))
        if shop is None:
            print(f"no shop with phone {phone}")
            return 1
        shop.pin_hash = hash_pin(pin)
        db.commit()
    print(f"PIN updated for {phone}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
