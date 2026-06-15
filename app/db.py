"""Database engine, session factory, and initialization."""
import os

from sqlalchemy import create_engine
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
