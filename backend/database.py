from __future__ import annotations

import os
from pathlib import Path

from db.schema import build_engine, build_session_factory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "evidentia.db"
DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}",
)

engine = build_engine(DATABASE_URL)
SessionLocal = build_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
