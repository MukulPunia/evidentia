from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship as orm_relationship,
    sessionmaker,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Generate an internal UUID primary key."""
    return str(uuid4())


def public_ref(prefix: str) -> str:
    """Generate a human-readable reference such as COM-1A2B3C4D."""
    return f"{prefix}-{uuid4().hex[:8].upper()}"


class Base(DeclarativeBase):
    pass


# ============================================================
# COMPANY
# ============================================================

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    ref: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        default=lambda: public_ref("COM"),
    )

    legal_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    registration_number: Mapped[Optional[str]] = mapped_column(
        String(120),
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    facilities: Mapped[list["Facility"]] = orm_relationship(
        back_populates="company",
    )

    cases: Mapped[list["Case"]] = orm_relationship(
        back_populates="company",
    )


# ============================================================
# FACILITY
# ============================================================

class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    ref: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        default=lambda: public_ref("FAC"),
    )

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    registration_number: Mapped[Optional[str]] = mapped_column(
        String(120),
    )

    location_text: Mapped[Optional[str]] = mapped_column(
        String(500),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    company: Mapped["Company"] = orm_relationship(
        back_populates="facilities",
    )

    cases: Mapped[list["Case"]] = orm_relationship(
        back_populates="facility",
    )


# ============================================================
# CASE
# ============================================================

class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    ref: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        default=lambda: public_ref("CAS"),
    )

    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )

    facility_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("facilities.id"),
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        default="open",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    company: Mapped["Company"] = orm_relationship(
        back_populates="cases",
    )

    facility: Mapped[Optional["Facility"]] = orm_relationship(
        back_populates="cases",
    )

    claims: Mapped[list["Claim"]] = orm_relationship(
        back_populates="case",
    )

    artifacts: Mapped[list["Artifact"]] = orm_relationship(
        back_populates="case",
    )

    facts: Mapped[list["Fact"]] = orm_relationship(
        back_populates="case",
    )

    nodes: Mapped[list["EvidenceNode"]] = orm_relationship(
        back_populates="case",
    )

    edges: Mapped[list["EvidenceEdge"]] = orm_relationship(
        back_populates="case",
    )


# ============================================================
# CLAIM
# ============================================================

class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    ref: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        default=lambda: public_ref("CLM"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    material: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    claimed_quantity: Mapped[Optional[str]] = mapped_column(
        String(80),
    )

    start_date: Mapped[Optional[str]] = mapped_column(
        String(40),
    )

    end_date: Mapped[Optional[str]] = mapped_column(
        String(40),
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
    )

    case: Mapped["Case"] = orm_relationship(
        back_populates="claims",
    )


# ============================================================
# ARTIFACT / DOCUMENT
# ============================================================

class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    ref: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        default=lambda: public_ref("ART"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    artifact_type: Mapped[Optional[str]] = mapped_column(
        String(80),
    )

    origin_class: Mapped[str] = mapped_column(
        String(60),
        default="unknown",
        nullable=False,
    )

    issuer_name: Mapped[Optional[str]] = mapped_column(
        String(255),
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    mime_type: Mapped[Optional[str]] = mapped_column(
        String(120),
    )

    storage_path: Mapped[Optional[str]] = mapped_column(
        String(1000),
    )

    derived_from_artifact_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("artifacts.id"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    case: Mapped["Case"] = orm_relationship(
        back_populates="artifacts",
    )

    derived_from: Mapped[Optional["Artifact"]] = orm_relationship(
        foreign_keys=[derived_from_artifact_id],
        remote_side=[id],
        back_populates="derived_children",
    )

    derived_children: Mapped[list["Artifact"]] = orm_relationship(
        foreign_keys=[derived_from_artifact_id],
        back_populates="derived_from",
    )

    facts: Mapped[list["Fact"]] = orm_relationship(
        back_populates="artifact",
    )

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "sha256",
            name="uq_artifact_case_sha256",
        ),
        Index(
            "ix_artifact_case_type",
            "case_id",
            "artifact_type",
        ),
    )


# ============================================================
# FACT
# ============================================================

class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    ref: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        default=lambda: public_ref("FCT"),
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("artifacts.id"),
        nullable=False,
        index=True,
    )

    page: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    field: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    quote: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    normalized_value: Mapped[Optional[str]] = mapped_column(
        String(120),
    )

    unit: Mapped[Optional[str]] = mapped_column(
        String(40),
    )

    confidence: Mapped[Optional[str]] = mapped_column(
        String(30),
    )

    grounding_state: Mapped[str] = mapped_column(
        String(40),
        default="unverified",
        nullable=False,
    )

    case: Mapped["Case"] = orm_relationship(
        back_populates="facts",
    )

    artifact: Mapped["Artifact"] = orm_relationship(
        back_populates="facts",
    )

    __table_args__ = (
        Index(
            "ix_fact_case_field",
            "case_id",
            "field",
        ),
    )


# ============================================================
# EVIDENCE NODE
# ============================================================

class EvidenceNode(Base):
    __tablename__ = "evidence_nodes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    node_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    entity_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    display_label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

    case: Mapped["Case"] = orm_relationship(
        back_populates="nodes",
    )

    outgoing_edges: Mapped[list["EvidenceEdge"]] = orm_relationship(
        foreign_keys="EvidenceEdge.source_node_id",
        back_populates="source_node",
    )

    incoming_edges: Mapped[list["EvidenceEdge"]] = orm_relationship(
        foreign_keys="EvidenceEdge.target_node_id",
        back_populates="target_node",
    )

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "node_type",
            "entity_id",
            name="uq_case_node_entity",
        ),
    )


# ============================================================
# EVIDENCE EDGE / RELATIONSHIP
# ============================================================

class EvidenceEdge(Base):
    __tablename__ = "evidence_edges"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_nodes.id"),
        nullable=False,
        index=True,
    )

    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_nodes.id"),
        nullable=False,
        index=True,
    )

    # IMPORTANT:
    # This is a database column, so we deliberately call
    # SQLAlchemy's relationship() helper "orm_relationship".
    relationship: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    basis: Mapped[Optional[str]] = mapped_column(
        Text,
    )

    confidence: Mapped[Optional[str]] = mapped_column(
        String(30),
    )

    case: Mapped["Case"] = orm_relationship(
        back_populates="edges",
    )

    source_node: Mapped["EvidenceNode"] = orm_relationship(
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )

    target_node: Mapped["EvidenceNode"] = orm_relationship(
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )

    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "source_node_id",
            "target_node_id",
            "relationship",
            name="uq_evidence_edge",
        ),
    )


# ============================================================
# DATABASE ENGINE
# ============================================================

def build_engine(
    database_url: str = "sqlite:///./data/evidentia.db",
):
    """
    Create the SQLAlchemy database engine.

    SQLite is used for local development.
    Production can later use PostgreSQL.
    """
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def build_session_factory(engine):
    """Create a SQLAlchemy session factory."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )