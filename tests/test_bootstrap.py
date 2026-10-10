from sqlalchemy import select, func

from db.bootstrap import init_db
from db.schema import (
    Case,
    Claim,
    Company,
    Facility,
    build_engine,
    build_session_factory,
)


def test_database_bootstrap_is_safe_to_run_twice(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh-evidentia.db"
    url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    init_db()
    init_db()

    engine = build_engine(url)
    SessionLocal = build_session_factory(engine)
    try:
        with SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(Company)) == 1
            assert session.scalar(select(func.count()).select_from(Facility)) == 1
            assert session.scalar(select(func.count()).select_from(Case)) == 1
            assert session.scalar(select(func.count()).select_from(Claim)) == 1
    finally:
        engine.dispose()
