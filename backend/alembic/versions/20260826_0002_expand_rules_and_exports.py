"""Expand trip rule snapshots and export cleanup metadata.

The initial web migration used ``create_all`` for the first deployment. This
revision keeps upgrades safe for databases that already reached that revision
by adding only columns that are absent, then creating the supporting indexes.
"""

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, Numeric, inspect


revision = "20260826_0002"
down_revision = "20260720_0001"
branch_labels = None
depends_on = None


def _add_if_missing(table: str, column: Column) -> None:
    inspector = inspect(op.get_bind())
    names = {item["name"] for item in inspector.get_columns(table)}
    if column.name not in names:
        op.add_column(table, column)


def _index_if_missing(name: str, table: str, columns: list[str]) -> None:
    inspector = inspect(op.get_bind())
    if not any(item["name"] == name for item in inspector.get_indexes(table)):
        op.create_index(name, table, columns)


def upgrade() -> None:
    _add_if_missing("trips", Column("include_start_day", Boolean(), nullable=False, server_default="1"))
    _add_if_missing("trips", Column("include_end_day", Boolean(), nullable=False, server_default="1"))
    _add_if_missing("trips", Column("lodging_limit_per_day", Numeric(12, 2), nullable=True))
    _add_if_missing("trips", Column("require_return_ticket", Boolean(), nullable=False, server_default="1"))
    _add_if_missing("trips", Column("require_lodging_invoice", Boolean(), nullable=False, server_default="1"))
    _add_if_missing("exports", Column("last_accessed_at", DateTime(timezone=True), nullable=True))
    _index_if_missing("ix_exports_last_accessed_at", "exports", ["last_accessed_at"])


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "last_accessed_at" in {item["name"] for item in inspector.get_columns("exports")}:
        op.drop_index("ix_exports_last_accessed_at", table_name="exports")
        op.drop_column("exports", "last_accessed_at")
    trip_columns = {item["name"] for item in inspector.get_columns("trips")}
    for name in (
        "require_lodging_invoice",
        "require_return_ticket",
        "lodging_limit_per_day",
        "include_end_day",
        "include_start_day",
    ):
        if name in trip_columns:
            op.drop_column("trips", name)
