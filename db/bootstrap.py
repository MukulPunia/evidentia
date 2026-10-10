
from __future__ import annotations

import os
import re
from pathlib import Path

from sqlalchemy import select

from .schema import (
    Base,
    Case,
    Claim,
    Company,
    Facility,
    build_engine,
    build_session_factory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEMO_CASE_TITLE = "E-waste Recycling Claim Demo"
DEMO_COMPANY_NAME = "Evidentia Recycling Solutions Pvt. Ltd."

DEMO_START_DATE = "2026-08-01"
DEMO_END_DATE = "2026-08-02"

OLD_DEMO_START_DATE = "2026-10-01"
OLD_DEMO_END_DATE = "2026-10-02"


def database_url() -> str:
    """Use DATABASE_URL or the project's default SQLite database."""
    configured = os.getenv("DATABASE_URL")

    if configured:
        return configured

    path = PROJECT_ROOT / "data" / "evidentia.db"
    path.parent.mkdir(parents=True, exist_ok=True)

    return f"sqlite:///{path.as_posix()}"


def _is_demo_quantity(value: str | None) -> bool:
    """Recognize the 20-tonne quantity used by the demo claim."""
    if not value:
        return False

    return bool(
        re.fullmatch(
            r"\s*20(?:\.0+)?\s*(?:t|tonnes?|tons?)?\s*",
            value,
            flags=re.IGNORECASE,
        )
    )


def _is_demo_material(value: str | None) -> bool:
    """Recognize e-waste without depending on capitalization or hyphens."""
    normalized = re.sub(
        r"[^a-z]",
        "",
        value or "",
        flags=re.IGNORECASE,
    ).lower()

    return normalized in {"ewaste", "electronicwaste"}


def seed_demo_data(engine) -> None:
    """
    Create the demo company, facility, case and claim when missing.

    Migrate only the known old date range on a matching demo claim.
    Do not change other claims or user-edited date ranges.
    """
    SessionLocal = build_session_factory(engine)

    with SessionLocal() as session:
        company = session.scalar(
            select(Company).where(
                Company.legal_name == DEMO_COMPANY_NAME
            )
        )

        if company is None:
            company = Company(
                legal_name=DEMO_COMPANY_NAME
            )
            session.add(company)
            session.flush()

        facility = session.scalar(
            select(Facility).where(
                Facility.company_id == company.id,
                Facility.name == "Demo Processing Facility",
            )
        )

        if facility is None:
            facility = Facility(
                company_id=company.id,
                name="Demo Processing Facility",
                location_text="Gurugram, India",
            )
            session.add(facility)
            session.flush()

        case = session.scalar(
            select(Case).where(
                Case.title == DEMO_CASE_TITLE,
                Case.company_id == company.id,
            )
        )

        if case is None:
            case = Case(
                company_id=company.id,
                facility_id=facility.id,
                title=DEMO_CASE_TITLE,
                status="open",
            )
            session.add(case)
            session.flush()

        claims = session.scalars(
            select(Claim).where(
                Claim.case_id == case.id
            )
        ).all()

        if not claims:
            # Seed the demo claim only when this case has no claims.
            session.add(
                Claim(
                    case_id=case.id,
                    material="E-waste",
                    claimed_quantity="20.0 t",
                    start_date=DEMO_START_DATE,
                    end_date=DEMO_END_DATE,
                    description="Demo recycling event claim",
                )
            )
        else:
            for claim in claims:
                is_demo_claim = (
                    _is_demo_material(claim.material)
                    and _is_demo_quantity(claim.claimed_quantity)
                )

                has_old_demo_dates = (
                    claim.start_date == OLD_DEMO_START_DATE
                    and claim.end_date == OLD_DEMO_END_DATE
                )

                if is_demo_claim and has_old_demo_dates:
                    claim.start_date = DEMO_START_DATE
                    claim.end_date = DEMO_END_DATE

        session.commit()


def init_db() -> None:
    """Create the database tables and initialize demo records."""
    engine = build_engine(database_url())

    try:
        Base.metadata.create_all(engine)
        seed_demo_data(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_db()
    print("Database ready.")
