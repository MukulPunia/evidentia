from __future__ import annotations

from typing import Any

from .models import Artifact, Fact


FIELD_ALIASES = {
    "quantity": "quantity_t",
    "quantity_t": "quantity_t",
    "certified_quantity": "quantity_t",
    "certificate_quantity": "quantity_t",
    "invoice_quantity": "quantity_t",
    "declared_quantity": "quantity_t",
    "recycling_quantity": "quantity_t",
    "net_transported_quantity": "quantity_t",
    "transported_quantity": "quantity_t",
    "transport_quantity": "quantity_t",
    "shipped_quantity": "quantity_t",
    "net_weight": "net_weight_t",
    "net_weight_t": "net_weight_t",
    "received_quantity": "net_weight_t",
    "receipt_quantity": "net_weight_t",
    "capacity": "capacity_t",
    "capacity_t": "capacity_t",
    "processing_capacity": "capacity_t",
    "facility_capacity": "capacity_t",
    "declared_capacity": "capacity_t",
    "declared_processing_capacity": "capacity_t",
    "validated_processing_capacity": "capacity_t",
    "maximum_processing_capacity": "capacity_t",
}


def normalize_fact_field(
    field: str,
) -> str:
    """
    Convert Gemini field names to the canonical engine schema.
    """

    normalized = (
        field
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    return FIELD_ALIASES.get(
        normalized,
        normalized,
    )


def normalize_source_text(
    value: str,
) -> str:
    """
    Normalize source and quote text so harmless differences in
    spacing, punctuation, and capitalization do not break grounding.
    """

    characters = []

    for char in (value or "").lower():
        if char.isalnum():
            characters.append(char)
        else:
            characters.append(" ")

    return " ".join(
        "".join(characters).split()
    )


def quote_is_grounded(
    fact: Fact,
    artifact: Artifact,
) -> bool:
    """
    Check whether Gemini's quote appears in the actual source page.
    """

    source_pages = artifact.metadata.get(
        "source_pages",
        [],
    )

    if not source_pages:
        return False

    if fact.page < 1 or fact.page > len(source_pages):
        return False

    page_text = source_pages[
        fact.page - 1
    ].get("text", "")

    source_normalized = normalize_source_text(
        page_text
    )

    quote_normalized = normalize_source_text(
        fact.quote
    )

    if not quote_normalized:
        return False

    return (
        quote_normalized
        in source_normalized
    )


def validate_fact(
    fact: Fact,
    artifacts: dict[str, Artifact],
) -> tuple[bool, str]:
    """
    Validate and canonicalize one Gemini-extracted fact.

    A fact can only become verified when its source quote is actually
    grounded in the corresponding PDF page.
    """

    artifact = artifacts.get(
        fact.artifact_id
    )

    if artifact is None:
        fact.validation_state = "rejected"
        return False, "artifact_not_found"

    fact.field = normalize_fact_field(
        fact.field
    )

    if fact.page < 1:
        fact.validation_state = "rejected"
        return False, "invalid_page"

    page_count = artifact.metadata.get(
        "page_count"
    )

    if (
        page_count is not None
        and fact.page > page_count
    ):
        fact.validation_state = "rejected"
        return False, "page_not_found"

    # Actual PDF source grounding.
    if not quote_is_grounded(
        fact,
        artifact,
    ):
        fact.validation_state = "rejected"
        return False, "quote_not_grounded"

    numeric_fields = {
        "quantity_t",
        "net_weight_t",
        "capacity_t",
    }

    if fact.field in numeric_fields:

        if fact.normalized_value is None:
            fact.validation_state = "rejected"
            return False, "missing_numeric_value"

        try:
            fact.normalized_value = float(
                fact.normalized_value
            )
        except (
            TypeError,
            ValueError,
        ):
            fact.validation_state = "rejected"
            return False, "invalid_numeric_value"

    if fact.unit:
        fact.unit = fact.unit.strip().lower()

        allowed_units = {
            "t",
            "kg",
            "tonne",
            "tonnes",
        }

        if fact.unit not in allowed_units:
            fact.validation_state = "rejected"
            return False, "unsupported_unit"

    fact.validation_state = "verified"

    return True, "verified"


def validate_extraction_coverage(
    artifacts: list[Artifact],
    raw_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Check whether every submitted artifact produced at least one
    extracted fact.
    """

    artifact_ids = {
        artifact.artifact_id
        for artifact in artifacts
    }

    extracted_artifact_ids = {
        str(fact.get("artifact_id"))
        for fact in raw_facts
        if fact.get("artifact_id")
    }

    covered_ids = (
        artifact_ids
        & extracted_artifact_ids
    )

    rows = []

    for artifact in artifacts:
        if artifact.artifact_id in covered_ids:
            rows.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "filename": artifact.filename,
                    "status": "covered",
                }
            )
        else:
            rows.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "filename": artifact.filename,
                    "status": "no_fact_extracted",
                }
            )

    expected = len(artifact_ids)
    covered = len(covered_ids)

    coverage_pct = (
        round(
            (covered / expected) * 100,
            1,
        )
        if expected
        else 100.0
    )

    return {
        "expected_artifacts": expected,
        "artifacts_with_facts": covered,
        "coverage_pct": coverage_pct,
        "complete": covered == expected,
        "artifacts": rows,
    }

def assess_artifact_periods(
    claim: Any,
    artifacts: list[Artifact],
) -> dict[str, Any]:
    """
    Compare dates stated in evidence documents with the selected claim period.

    A document is eligible for period-dependent calculations only when its
    dates overlap the claim period. An undated document is not automatically
    treated as relevant.

    This function records the result in artifact.metadata["period_check"].
    The upload pipeline must apply that result before calculating support.
    """
    from datetime import date
    import re

    iso_date_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
    numeric_date_pattern = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
    textual_date_patterns = [
        re.compile(r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s*,?\s+(\d{4})\b", re.IGNORECASE),
        re.compile(r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b", re.IGNORECASE),
    ]
    range_pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2})"
        r"\s*(?:to|through|until|–|—|-)\s*"
        r"(\d{4}-\d{2}-\d{2})",
        flags=re.IGNORECASE,
    )
    year_pattern = re.compile(r"(?<![\d/.-])(19\d{2}|20\d{2}|21\d{2})(?![\d/.-])")
    month_map = {
        name.lower(): month for month, names in enumerate([
            (), ("Jan", "January"), ("Feb", "February"), ("Mar", "March"),
            ("Apr", "April"), ("May",), ("Jun", "June"), ("Jul", "July"),
            ("Aug", "August"), ("Sep", "September"), ("Oct", "October"),
            ("Nov", "November"), ("Dec", "December")
        ]) if month for name in names
    }

    def parse_date(value: Any) -> date | None:
        if not isinstance(value, str) or not value.strip():
            return None

        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None

    jurisdiction = str(getattr(claim, "jurisdiction", None) or "").lower()
    # Use the facility's recorded location as a formatting hint only. If the
    # location is absent, default to day-first (India/UK/EU convention) and
    # preserve a note so reviewers can verify ambiguous values.
    us_date_order = any(token in jurisdiction for token in ("united states", "usa", "u.s.a.", "america"))

    claim_start = parse_date(
        getattr(claim, "period_start", None)
    )
    claim_end = parse_date(
        getattr(claim, "period_end", None)
    )

    if claim_start and claim_end and claim_start > claim_end:
        claim_start, claim_end = claim_end, claim_start

    artifact_map = {
        artifact.artifact_id: artifact
        for artifact in artifacts
    }

    cache: dict[
        str,
        tuple[list[date], list[tuple[date, date]], str]
    ] = {}

    def dates_for(
        artifact: Artifact,
        visited: set[str] | None = None,
    ) -> tuple[list[date], list[tuple[date, date]], str]:
        artifact_id = artifact.artifact_id

        if artifact_id in cache:
            return cache[artifact_id]

        visited = set() if visited is None else set(visited)

        if artifact_id in visited:
            return [], [], "undated"

        visited.add(artifact_id)

        text = artifact.text or ""

        found_dates: list[date] = []
        numeric_date_used = False
        numeric_date_order = "MM/DD/YYYY" if us_date_order else "DD/MM/YYYY"
        for value in iso_date_pattern.findall(text):
            parsed = parse_date(value)
            if parsed is not None and parsed not in found_dates:
                found_dates.append(parsed)

        # Common international numeric dates are interpreted as day/month/year
        # (India/UK/EU convention). The result exposes this as a parser note so
        # reviewers can verify ambiguous dates against the source country.
        for first_text, second_text, year_text in numeric_date_pattern.findall(text):
            try:
                if us_date_order:
                    parsed = date(int(year_text), int(first_text), int(second_text))
                else:
                    parsed = date(int(year_text), int(second_text), int(first_text))
                numeric_date_used = True
            except ValueError:
                # If the recorded US order is invalid, try day-first; this
                # handles unambiguous values such as 31/12/2020.
                try:
                    parsed = date(int(year_text), int(second_text), int(first_text))
                    numeric_date_used = True
                    numeric_date_order = "DD/MM/YYYY (unambiguous fallback)"
                except ValueError:
                    continue
            if parsed not in found_dates:
                found_dates.append(parsed)

        for pattern_index, pattern in enumerate(textual_date_patterns):
            for match in pattern.finditer(text):
                parts = match.groups()
                try:
                    if pattern_index == 0:
                        day_text, month_text, year_text = parts
                    else:
                        month_text, day_text, year_text = parts
                    month = month_map[month_text[:3].lower()]
                    parsed = date(int(year_text), month, int(day_text))
                except (ValueError, KeyError):
                    continue
                if parsed not in found_dates:
                    found_dates.append(parsed)

        found_ranges: list[tuple[date, date]] = []

        for start_text, end_text in range_pattern.findall(text):
            range_start = parse_date(start_text)
            range_end = parse_date(end_text)

            if range_start is None or range_end is None:
                continue

            if range_start > range_end:
                range_start, range_end = range_end, range_start

            found_ranges.append((range_start, range_end))

        # For annual reporting periods, a bare year is useful only when the
        # selected claim covers that entire calendar year. It must not be used
        # as the date of a specific shipment.
        found_years = sorted({int(value) for value in year_pattern.findall(text)})

        # Use dates printed on this document whenever available.
        if found_dates or found_ranges:
            result = (
                sorted(found_dates),
                found_ranges,
                (f"document; numeric date interpreted as {numeric_date_order}" if numeric_date_used else "document"),
            )
            cache[artifact_id] = result
            return result

        # Only inherit dates through an already-established relationship.
        parent = artifact_map.get(artifact.derived_from or "")

        if parent is not None:
            parent_dates, parent_ranges, _ = dates_for(
                parent,
                visited,
            )

            if parent_dates or parent_ranges:
                result = (
                    parent_dates,
                    parent_ranges,
                    f"inherited:{parent.artifact_id}",
                )
                cache[artifact_id] = result
                return result

        annual_ranges: list[tuple[date, date]] = []
        for year in found_years:
            start_of_year = date(year, 1, 1)
            end_of_year = date(year, 12, 31)
            # Only record year-only periods when the claim period covers
            # the complete year; partial periods need a real event date.
            if claim_start and claim_end and claim_start <= start_of_year and claim_end >= end_of_year:
                annual_ranges.append((start_of_year, end_of_year))

        if annual_ranges:
            result = ([], annual_ranges, "annual_reporting_year")
            cache[artifact_id] = result
            return result

        result = ([], [], "undated")
        cache[artifact_id] = result
        return result

    rows: list[dict[str, Any]] = []

    for artifact in artifacts:
        dates, date_ranges, date_source = dates_for(artifact)

        if claim_start is None or claim_end is None:
            status = "claim_period_unavailable"
            eligible = False

        elif not dates and not date_ranges:
            status = "undated"
            eligible = False

        else:
            date_overlap = any(
                claim_start <= value <= claim_end
                for value in dates
            )

            range_overlap = any(
                start <= claim_end and end >= claim_start
                for start, end in date_ranges
            )

            eligible = date_overlap or range_overlap
            status = "in_period" if eligible else "out_of_period"

        row = {
            "artifact_id": artifact.artifact_id,
            "filename": artifact.filename,
            "status": status,
            "eligible_for_calculation": eligible,
            "dates_found": [
                value.isoformat()
                for value in dates
            ],
            "date_ranges_found": [
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
                for start, end in date_ranges
            ],
            "date_source": date_source,
        }

        if dates:
            row["document_start"] = min(dates).isoformat()
            row["document_end"] = max(dates).isoformat()
        elif date_ranges:
            row["document_start"] = min(
                start for start, _ in date_ranges
            ).isoformat()
            row["document_end"] = max(
                end for _, end in date_ranges
            ).isoformat()

        artifact.metadata["period_check"] = row
        rows.append(row)

    return {
        "claim_period": {
            "start": claim_start.isoformat() if claim_start else None,
            "end": claim_end.isoformat() if claim_end else None,
        },
        "in_period_count": sum(
            row["status"] == "in_period"
            for row in rows
        ),
        "out_of_period_count": sum(
            row["status"] == "out_of_period"
            for row in rows
        ),
        "undated_count": sum(
            row["status"] == "undated"
            for row in rows
        ),
        "claim_period_available": (
            claim_start is not None and claim_end is not None
        ),
        "documents": rows,
    }
