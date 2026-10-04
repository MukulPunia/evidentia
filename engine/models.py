from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


ORIGIN_CLASSES = {
    "claimant_recycler",
    "counterparty",
    "independent_system",
    "regulator_reference",
}


@dataclass
class Claim:
    claim_id: str
    material: str
    quantity_t: float
    facility_id: str
    period_start: str
    period_end: str


@dataclass
class Artifact:
    artifact_id: str
    artifact_type: str
    filename: str
    origin_class: str
    issuer: str

    # Existing extracted/fixture text.
    text: str = ""

    # Provenance relationship.
    derived_from: Optional[str] = None

    # New: actual file information for real evidence ingestion.
    local_path: Optional[str] = None
    mime_type: Optional[str] = None
    sha256: Optional[str] = None

    # Flexible metadata for page count, upload source, EXIF, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fact:
    fact_id: str
    artifact_id: str
    page: int
    field: str
    quote: str
    normalized_value: Any
    unit: Optional[str]

    confidence: str = "high"
    validation_state: str = "verified"


@dataclass
class StageResult:
    stage: str
    evidence_description: str
    origin: str
    independent: Optional[bool]
    value_t: Optional[float]
    status: str
    gap: str = ""


@dataclass
class SupportEnvelope:
    claimed_t: float
    evidence_supported_t: float
    final_supportable_t: float
    binding_constraint: str
    assumptions: List[str]

    custody_gap_t: float = 0.0
    receipt_conflict: bool = False
    stages: List[StageResult] = field(default_factory=list)


@dataclass
class CaseResult:
    claim: Claim
    facts: List[Fact]
    findings: List[Dict[str, Any]]
    envelope: SupportEnvelope
    provenance_links: List[Dict[str, Any]]