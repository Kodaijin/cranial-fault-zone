"""Database engine, session factory, and initialization."""
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Database location. Defaults to the Docker volume mount at /data; falls back to a
# local file when running outside the container (e.g. for tests).
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/cranial.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db():
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the data directory and all tables if they do not yet exist."""
    # Ensure the directory for the SQLite file exists.
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Import models so they register on Base.metadata before create_all.
    from app.models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate() -> None:
    """Idempotent, lightweight column migrations for SQLite.

    create_all() only creates missing *tables*, never new columns, so columns
    added in an update must be applied to already-deployed databases by hand.
    Each ALTER is guarded by a PRAGMA check so it is safe to run on every start.
    """
    # column name -> SQLite column definition for ALTER TABLE ADD COLUMN.
    entries_columns = {
        "end_time": "end_time DATETIME",
        "is_ongoing": "is_ongoing INTEGER NOT NULL DEFAULT 0",
        "linked_entry_id": "linked_entry_id INTEGER REFERENCES entries(id)",
        "auto_generated": "auto_generated INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as conn:
        existing = {
            row[1] for row in conn.execute(text("PRAGMA table_info(entries)"))
        }
        for name, ddl in entries_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE entries ADD COLUMN {ddl}"))
