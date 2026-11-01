"""voice turn state: pending/response json, total latency; one ledger row per voice event

Revision ID: 7c1e2d9a4b10
Revises: 3afc0ce52fe2
Create Date: 2026-11-01

Note: uses CREATE UNIQUE INDEX instead of altering ledger_entry. On SQLite an ALTER in batch
mode recreates the table, which would silently drop the append-only triggers.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c1e2d9a4b10"
down_revision: str | None = "3afc0ce52fe2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("voice_event", sa.Column("latency_total_ms", sa.Integer(), nullable=True))
    op.add_column("voice_event", sa.Column("pending_json", sa.JSON(), nullable=True))
    op.add_column("voice_event", sa.Column("response_json", sa.JSON(), nullable=True))
    op.create_index("uq_ledger_entry_voice_event", "ledger_entry", ["voice_event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_ledger_entry_voice_event", table_name="ledger_entry")
    with op.batch_alter_table("voice_event") as batch:  # voice_event has no triggers
        batch.drop_column("response_json")
        batch.drop_column("pending_json")
        batch.drop_column("latency_total_ms")
