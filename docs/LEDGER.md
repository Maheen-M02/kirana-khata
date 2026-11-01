# Ledger (Phase 3)

The code lives in `backend/app/ledger/`: `models.py`, `service.py` (writes) and `queries.py` (reads). The migration is `backend/alembic/versions/3afc0ce52fe2_*`.

## Rules, and where each is enforced

| Rule | Service | ORM | Database |
|---|---|---|---|
| Money is an integer number of paise | `check_amount` refuses float, bool, Decimal, str, 0, and > ₹1 crore | `BigInteger` columns | CHECK on the amount's sign |
| Append-only (no UPDATE or DELETE) | Never issues one | `before_update`/`before_delete` listeners raise `AppendOnlyViolationError` | **Triggers** on `ledger_entry` and `ledger_line` (SQLite: `RAISE(ABORT)`; Postgres: row triggers for UPDATE/DELETE plus a TRUNCATE trigger) |
| Corrections are reversals | `reverse_entry` / `undo_last` append a mirror row | n/a | `UNIQUE(reverses_entry_id)`: at most one reversal per entry |
| Credit and payment need a customer | `customer_required` | n/a | CHECK `ck_ledger_entry_customer_required` |
| Shops never see each other's data | Every function takes `shop_id`; cross-shop ids return 404 | n/a | n/a |

### Deviation from MASTER_PROMPT §5: `reversed_by`

The spec puts `reversed_by` on the original row, which would mean **updating** it. Instead, the reversal row carries `reverses_entry_id`, and "reversed by" is derived from that link (`queries.reversed_by`, exposed as `reversed_by` in the API). This keeps the table strictly insert-only, so the database triggers can forbid every UPDATE.

A reversal has the **same type** as the original and the **negated amount**, so every SUM nets out with no special cases:

```
balance(customer) = SUM(credit_sale) − SUM(payment_received) + SUM(adjustment)     -- in SQL
sales today       = SUM(cash_sale + credit_sale) for the IST day                   -- reversals included
```

- **"Aaj" means the Asia/Kolkata day:** `day_bounds_utc` converts the IST midnight-to-midnight window to UTC.
- **Postgres** returns `NUMERIC` for `SUM(bigint)`, so every sum is cast back to `BIGINT` and stays an exact Python `int`.
- **Cancellations:** a sale cancelled on a later day reduces the total of the day it was cancelled. This is noted for the end-of-day summary.

## Evidence

- **Property tests** (Hypothesis, 40 examples each): random sequences of credits, payments, cash sales, signed adjustments, reversals and undos.
  - The SQL balance always equals an independent Python model.
  - The total of all balances equals the model total.
  - Balances are always `int`.
  - The row count never shrinks.
  - Any entry plus its reversal equals 0.
- **Database guarantees:** raw `UPDATE`/`DELETE` SQL is refused by the triggers on both SQLite and Postgres. Invalid inserts are refused by the CHECK constraints.
- **Postgres in CI:** the whole ledger suite runs twice in CI (SQLite and a Postgres 16 service). Locally: `TEST_DATABASE_URL=postgresql://... make test`.
