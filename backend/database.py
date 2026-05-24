"""SQLAlchemy database engine and session configuration."""

import os
from sqlalchemy import inspect, text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import settings

# Ensure the data directory exists
db_dir = os.path.dirname(settings.DB_PATH)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

DATABASE_URL = f"sqlite:///{settings.DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called on startup."""
    # Import all models so they register with Base.metadata
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    """Apply tiny additive SQLite migrations for local existing databases."""
    inspector = inspect(engine)
    if "review_issues" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("review_issues")}
    statements: list[str] = []
    if "resolution_status" not in columns:
        statements.append(
            "ALTER TABLE review_issues "
            "ADD COLUMN resolution_status VARCHAR(50) NOT NULL DEFAULT 'OPEN'"
        )
    if "resolution_note" not in columns:
        statements.append(
            "ALTER TABLE review_issues ADD COLUMN resolution_note VARCHAR(2000)"
        )

    if not statements:
        return

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
