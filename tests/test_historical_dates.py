from engine.models import Artifact, Claim
from engine.validator import assess_artifact_periods


def test_day_first_numeric_date_is_recognized_for_india_style_date():
    claim = Claim("CLM-2020", "paper/cardboard", 1, "FAC-1", "2020-01-01", "2020-12-31")
    artifact = Artifact("DOC-1", "unknown", "record.pdf", "unknown", "Issuer", "Event date: 15/06/2020")

    result = assess_artifact_periods(claim, [artifact])

    assert result["documents"][0]["status"] == "in_period"
    assert result["documents"][0]["dates_found"] == ["2020-06-15"]


def test_historical_claim_year_is_not_limited_to_current_year():
    claim = Claim("CLM-2010", "paper/cardboard", 1, "FAC-1", "2010-01-01", "2010-12-31")
    artifact = Artifact("DOC-OLD", "unknown", "record.pdf", "unknown", "Issuer", "Report year 2010")

    result = assess_artifact_periods(claim, [artifact])

    assert result["documents"][0]["status"] == "in_period"
    assert result["documents"][0]["date_source"] == "annual_reporting_year"


def test_historical_year_is_not_used_for_a_specific_day_claim():
    claim = Claim("CLM-DAY", "paper/cardboard", 1, "FAC-1", "2010-06-15", "2010-06-15")
    artifact = Artifact("DOC-YEAR", "unknown", "record.pdf", "unknown", "Issuer", "Report year 2010")

    result = assess_artifact_periods(claim, [artifact])

    assert result["documents"][0]["status"] == "undated"
    assert result["documents"][0]["eligible_for_calculation"] is False


def test_ambiguous_numeric_date_uses_recorded_us_facility_location():
    claim = Claim("CLM-US", "paper/cardboard", 1, "FAC-US", "2020-01-01", "2020-12-31", jurisdiction="United States")
    artifact = Artifact("DOC-US", "unknown", "record.pdf", "unknown", "Issuer", "Event date: 06/07/2020")

    result = assess_artifact_periods(claim, [artifact])

    assert result["documents"][0]["dates_found"] == ["2020-06-07"]
    assert "MM/DD/YYYY" in result["documents"][0]["date_source"]


def test_ambiguous_numeric_date_defaults_day_first_without_us_jurisdiction():
    claim = Claim("CLM-IN", "paper/cardboard", 1, "FAC-IN", "2020-01-01", "2020-12-31", jurisdiction="India")
    artifact = Artifact("DOC-IN", "unknown", "record.pdf", "unknown", "Issuer", "Event date: 06/07/2020")

    result = assess_artifact_periods(claim, [artifact])

    assert result["documents"][0]["dates_found"] == ["2020-07-06"]
    assert "DD/MM/YYYY" in result["documents"][0]["date_source"]
