from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.schema import Case, Claim, Company, Facility
from backend.database import get_db

router = APIRouter(
    prefix="/api",
    tags=["Case Management"],
)


class CompanyCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    registration_number: Optional[str] = None


class FacilityCreate(BaseModel):
    company_id: str
    name: str = Field(min_length=1, max_length=255)
    registration_number: Optional[str] = None
    location_text: Optional[str] = None


class CaseCreate(BaseModel):
    company_id: str
    facility_id: Optional[str] = None
    title: str = Field(min_length=1, max_length=255)


class ClaimCreate(BaseModel):
    material: str = Field(min_length=1, max_length=120)
    claimed_quantity: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


def find_company(db: Session, company_id: str) -> Optional[Company]:
    company = db.get(Company, company_id)

    if company is not None:
        return company

    return db.scalar(
        select(Company).where(Company.ref == company_id)
    )


def find_facility(db: Session, facility_id: str) -> Optional[Facility]:
    facility = db.get(Facility, facility_id)

    if facility is not None:
        return facility

    return db.scalar(
        select(Facility).where(Facility.ref == facility_id)
    )


def find_case(db: Session, case_id: str) -> Optional[Case]:
    case = db.get(Case, case_id)

    if case is not None:
        return case

    return db.scalar(
        select(Case).where(Case.ref == case_id)
    )


@router.post("/companies")
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
):
    existing = None

    if payload.registration_number:
        existing = db.scalar(
            select(Company).where(
                Company.registration_number == payload.registration_number
            )
        )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="A company with this registration number already exists.",
        )

    company = Company(
        legal_name=payload.legal_name,
        registration_number=payload.registration_number,
    )

    db.add(company)
    db.commit()
    db.refresh(company)

    return {
        "status": "created",
        "company_id": company.id,
        "company_ref": company.ref,
        "legal_name": company.legal_name,
        "registration_number": company.registration_number,
    }


@router.post("/facilities")
def create_facility(
    payload: FacilityCreate,
    db: Session = Depends(get_db),
):
    company = find_company(db, payload.company_id)

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found.",
        )

    facility = Facility(
        company_id=company.id,
        name=payload.name,
        registration_number=payload.registration_number,
        location_text=payload.location_text,
    )

    db.add(facility)
    db.commit()
    db.refresh(facility)

    return {
        "status": "created",
        "facility_id": facility.id,
        "facility_ref": facility.ref,
        "company_id": company.id,
        "company_ref": company.ref,
        "name": facility.name,
        "location_text": facility.location_text,
    }


@router.post("/cases")
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
):
    company = find_company(db, payload.company_id)

    if company is None:
        raise HTTPException(
            status_code=404,
            detail="Company not found.",
        )

    facility = None

    if payload.facility_id:
        facility = find_facility(db, payload.facility_id)

        if facility is None:
            raise HTTPException(
                status_code=404,
                detail="Facility not found.",
            )

        if facility.company_id != company.id:
            raise HTTPException(
                status_code=400,
                detail="Facility does not belong to the supplied company.",
            )

    case = Case(
        company_id=company.id,
        facility_id=facility.id if facility else None,
        title=payload.title,
        status="open",
    )

    db.add(case)
    db.commit()
    db.refresh(case)

    return {
        "status": "created",
        "case_id": case.id,
        "case_ref": case.ref,
        "company_id": company.id,
        "company_ref": company.ref,
        "facility_id": facility.id if facility else None,
        "facility_ref": facility.ref if facility else None,
        "title": case.title,
        "status_value": case.status,
    }


@router.post("/cases/{case_id}/claims")
def create_claim(
    case_id: str,
    payload: ClaimCreate,
    db: Session = Depends(get_db),
):
    case = find_case(db, case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    claim = Claim(
        case_id=case.id,
        material=payload.material,
        claimed_quantity=payload.claimed_quantity,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )

    db.add(claim)
    db.commit()
    db.refresh(claim)

    return {
        "status": "created",
        "claim_id": claim.id,
        "claim_ref": claim.ref,
        "case_id": case.id,
        "case_ref": case.ref,
        "material": claim.material,
        "claimed_quantity": claim.claimed_quantity,
        "start_date": claim.start_date,
        "end_date": claim.end_date,
    }


@router.get("/cases")
def list_cases(db: Session = Depends(get_db)):
    """Return the cases and claims available in the workspace."""
    cases = db.scalars(select(Case).order_by(Case.created_at.desc())).all()
    return {
        "cases": [
            {
                "id": case.id,
                "ref": case.ref,
                "title": case.title,
                "status": case.status,
                "company": {
                    "id": case.company.id,
                    "ref": case.company.ref,
                    "name": case.company.legal_name,
                },
                "facility": (
                    {
                        "id": case.facility.id,
                        "ref": case.facility.ref,
                        "name": case.facility.name,
                        "location": case.facility.location_text,
                    }
                    if case.facility
                    else None
                ),
                "claims": [
                    {
                        "id": claim.id,
                        "ref": claim.ref,
                        "material": claim.material,
                        "claimed_quantity": claim.claimed_quantity,
                        "start_date": claim.start_date,
                        "end_date": claim.end_date,
                    }
                    for claim in sorted(
                        case.claims,
                        key=lambda item: item.ref,
                    )
                ],
            }
            for case in cases
        ]
    }


@router.get("/cases/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
):
    case = find_case(db, case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found.",
        )

    return {
        "case_id": case.id,
        "case_ref": case.ref,
        "title": case.title,
        "status": case.status,
        "company": {
            "id": case.company.id,
            "ref": case.company.ref,
            "legal_name": case.company.legal_name,
        },
        "facility": (
            {
                "id": case.facility.id,
                "ref": case.facility.ref,
                "name": case.facility.name,
                "location": case.facility.location_text,
            }
            if case.facility
            else None
        ),
        "claims": [
            {
                "id": claim.id,
                "ref": claim.ref,
                "material": claim.material,
                "claimed_quantity": claim.claimed_quantity,
                "start_date": claim.start_date,
                "end_date": claim.end_date,
            }
            for claim in case.claims
        ],
        "artifact_count": len(case.artifacts),
        "fact_count": len(case.facts),
        "graph_node_count": len(case.nodes),
        "graph_edge_count": len(case.edges),
    }