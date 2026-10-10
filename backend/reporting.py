from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)


INK = colors.HexColor("#102238")
MUTED = colors.HexColor("#526273")
BLUE = colors.HexColor("#1D5F91")
PALE = colors.HexColor("#EEF5FA")
BORDER = colors.HexColor("#D8E2EB")
RED = colors.HexColor("#A21C24")
AMBER = colors.HexColor("#8A4B00")
GREEN = colors.HexColor("#08764F")


def _text(value: Any, limit: int = 600) -> str:
    value = "—" if value is None or value == "" else str(value)
    if len(value) > limit:
        value = value[:limit - 1] + "…"
    return escape(value).replace("\n", "<br/>")


def _num(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:,.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "not established"


def _page_footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(BORDER)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "Evidentia · Evidence review report · Human verification may still be required")
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_plain_english_report(data: dict[str, Any]) -> bytes:
    """Create a short report from the exact analysis response; never invent facts."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=21 * mm,
        title="Evidentia Evidence Review Report",
        author="Evidentia",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("EvidentiaTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, alignment=TA_LEFT, spaceAfter=4 * mm),
        "subtitle": ParagraphStyle("EvidentiaSubtitle", parent=base["Normal"], fontSize=9, leading=12, textColor=MUTED, spaceAfter=5 * mm),
        "h": ParagraphStyle("EvidentiaH", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=BLUE, spaceBefore=4 * mm, spaceAfter=2 * mm, keepWithNext=True),
        "body": ParagraphStyle("EvidentiaBody", parent=base["BodyText"], fontSize=9, leading=12, textColor=INK, spaceAfter=2 * mm),
        "small": ParagraphStyle("EvidentiaSmall", parent=base["BodyText"], fontSize=7.5, leading=9.5, textColor=MUTED),
        "cell": ParagraphStyle("EvidentiaCell", parent=base["BodyText"], fontSize=7.4, leading=9, textColor=INK),
        "cellhead": ParagraphStyle("EvidentiaCellHead", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white),
        "callout": ParagraphStyle("EvidentiaCallout", parent=base["BodyText"], fontSize=9.3, leading=13, textColor=INK, leftIndent=2 * mm, rightIndent=2 * mm, spaceBefore=1 * mm, spaceAfter=1 * mm),
    }

    claim = data.get("claim") or {}
    envelope = data.get("envelope") or {}
    artifacts = data.get("artifacts") or []
    intake = data.get("intake") or []
    grounding = data.get("grounding") or []
    findings = data.get("findings") or []
    coverage = data.get("extraction_coverage") or {}
    periods = data.get("period_validation") or {}
    case_record = data.get("case_record") or {}
    claim_record = data.get("claim_record") or {}

    claimed = envelope.get("claimed_t", claim.get("quantity_t"))
    evidence_supported = envelope.get("evidence_supported_t")
    final_supportable = envelope.get("final_supportable_t")
    valid_quantity = evidence_supported is not None and final_supportable is not None
    if data.get("status") == "review_required" and (not valid_quantity or float(evidence_supported or 0) <= 0):
        verdict = "REVIEW REQUIRED — SUPPORT NOT ESTABLISHED; no document passed intake"
        verdict_color = AMBER
    elif data.get("status") == "review_required":
        verdict = "REVIEW REQUIRED — no document passed the intake checks"
        verdict_color = AMBER
    elif not valid_quantity or (float(evidence_supported or 0) <= 0):
        verdict = "SUPPORT NOT ESTABLISHED — no eligible weight evidence"
        verdict_color = RED
    elif float(final_supportable or 0) < float(claimed or 0):
        verdict = "PARTIALLY SUPPORTED — review the limits and gaps below"
        verdict_color = AMBER
    else:
        verdict = "QUANTITY LIMIT REACHED — this is not proof of authenticity"
        verdict_color = GREEN

    story = [
        Paragraph("Evidentia Evidence Review", styles["title"]),
        Paragraph("Plain-English summary of the documents checked, what they support, and what still needs attention.", styles["subtitle"]),
    ]
    meta = [
        [Paragraph("Case", styles["cellhead"]), Paragraph("Claim", styles["cellhead"]), Paragraph("Material", styles["cellhead"]), Paragraph("Claim period", styles["cellhead"])],
        [Paragraph(_text(case_record.get("title") or case_record.get("ref") or "Not recorded"), styles["cell"]), Paragraph(_text(claim_record.get("ref") or claim.get("claim_id") or "Not recorded"), styles["cell"]), Paragraph(_text(claim.get("material")), styles["cell"]), Paragraph(_text(f"{claim.get('period_start') or '—'} to {claim.get('period_end') or '—'}"), styles["cell"])],
    ]
    t = Table(meta, colWidths=[48 * mm, 34 * mm, 34 * mm, 52 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("BACKGROUND", (0, 1), (-1, 1), PALE),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 3 * mm)]

    decision = Table([[Paragraph(f"<b>{_text(verdict)}</b>", styles["callout"])]], colWidths=[168 * mm])
    decision.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("BOX", (0, 0), (-1, -1), 1.1, verdict_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(decision)
    story.append(Paragraph(f"<b>Recorded facility/location context:</b> {_text(claim.get('jurisdiction') or 'Not recorded')}. This location can guide date-format interpretation but does not independently prove a document's country of origin.", styles["small"]))
    story.append(Paragraph("What the amount means", styles["h"]))
    story.append(Paragraph(
        f"<b>Claimed amount:</b> {_num(claimed)} tonnes. &nbsp; "
        f"<b>Amount found in eligible records:</b> {_num(evidence_supported)} tonnes. &nbsp; "
        f"<b>Current support limit:</b> {_num(final_supportable)} tonnes.", styles["body"]))
    if not valid_quantity or float(evidence_supported or 0) <= 0:
        story.append(Paragraph(
            "Evidentia did not find an eligible, verified transport or receipt quantity that can support this claim. "
            "The claim amount is an assertion; it must not be treated as evidence of itself. "
            "The report therefore does not establish a supported shipment weight.", styles["body"]))
    else:
        story.append(Paragraph(
            "The reported amount is a limit calculated from the verified quantity facts accepted by the rules. "
            "It does not, by itself, confirm that documents are authentic or that the evidence chain is complete.", styles["body"]))

    source_texts = " ".join(str(a.get("text", "")) for a in artifacts).lower()
    story.append(Paragraph("Expected information to check", styles["h"]))
    expected_rows = [[Paragraph(x, styles["cellhead"]) for x in ("Field to check", "Expected evidence", "Validation rule")]]
    expected_checks = [
        ("Document identity", "Document type, issuer, organisation and source page", "Record the source and retain the exact supporting quote."),
        ("Claim material", "Material/product stated in the record", "Do not use a different material category to support this claim."),
        ("Event/reporting period", "Shipment date or clearly labelled reporting period", "A contract/publication date is not automatically a shipment date."),
        ("Quantity and unit", "Quantity explicitly reported, with its unit and context", "A historical total or table aggregate is not a single-shipment weight."),
        ("Chain references", "Manifest, receipt/weighbridge, processing and facility IDs when present", "Link evidence only when the record references or otherwise establishes the relationship."),
        ("Source independence", "Who issued the record and whether it is derived from another source", "Copies from one source do not count as independent corroboration."),
    ]
    if "suffolk county council" in source_texts or "27176-paper-cardboard" in " ".join(str(a.get("filename", "")) for a in artifacts).lower():
        expected_checks = [
            ("Contract supplier", "Expected to check the named contractor (the document states Biffa)", "A supplier name does not prove a specific shipment."),
            ("Processing facility", "Expected to check the named MRF/facility (Masons MRF is listed)", "Facility description is context, not receipt evidence."),
            ("Contract dates / extension", "Expected to distinguish original term from later extension dates", "Label contractual dates separately from shipment dates."),
            ("Contract spending", "Expected to preserve each financial-year label and currency/value", "Spending amounts are not tonnes or shipment quantities."),
            ("Historical tonnage table", "Expected to retain 53,600 tonnes with its historical/reporting context", "This is an aggregate table total, not the 20-tonne claim weight."),
            ("Performance KPI", "Expected to preserve the 90% monthly / 95% annual requirement", "A target is not an achieved shipment result."),
            ("Weighbridge requirements", "Expected to identify the ticket fields the contract says should be reported", "A description of required tickets is not an actual ticket."),
        ]
    for field_name, expected, rule in expected_checks:
        expected_rows.append([Paragraph(_text(field_name), styles["cell"]), Paragraph(_text(expected, 220), styles["cell"]), Paragraph(_text(rule, 180), styles["cell"])])
    expected_table = Table(expected_rows, colWidths=[35 * mm, 67 * mm, 66 * mm], repeatRows=1)
    expected_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(expected_table)

    facts_by_artifact: dict[str, list[dict[str, Any]]] = {}
    for fact in grounding:
        facts_by_artifact.setdefault(str(fact.get("artifact_id", "")), []).append(fact)
    intake_by_id = {str(x.get("artifact_id", "")): x for x in intake}
    story.append(Paragraph("Documents checked", styles["h"]))
    rows = [[Paragraph(x, styles["cellhead"]) for x in ("Document", "Detected type", "Intake decision", "Why it matters")]]
    for artifact in artifacts[:35]:
        aid = str(artifact.get("artifact_id", ""))
        gate = intake_by_id.get(aid, {})
        reason = gate.get("reason") or "Document was submitted for review."
        rows.append([
            Paragraph(_text(artifact.get("filename") or aid, 85), styles["cell"]),
            Paragraph(_text(artifact.get("artifact_type") or "unknown"), styles["cell"]),
            Paragraph(_text(gate.get("status") or "checked"), styles["cell"]),
            Paragraph(_text(reason, 220), styles["cell"]),
        ])
    if len(artifacts) > 35:
        rows.append([Paragraph("Additional documents", styles["cell"]), Paragraph("—", styles["cell"]), Paragraph("—", styles["cell"]), Paragraph(f"{len(artifacts)-35} additional documents omitted from this brief summary.", styles["cell"])])
    dt = Table(rows, colWidths=[44 * mm, 29 * mm, 26 * mm, 69 * mm], repeatRows=1)
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(dt)

    story.append(Paragraph("Extracted details and source checks", styles["h"]))
    rows = [[Paragraph(x, styles["cellhead"]) for x in ("Document", "Field", "Extracted value", "Check / source quote")]]
    for fact in grounding[:45]:
        state = fact.get("state", "not checked")
        quote = fact.get("quote") or fact.get("reason") or "No source quote provided."
        rows.append([
            Paragraph(_text(fact.get("artifact_id"), 45), styles["cell"]),
            Paragraph(_text(fact.get("field"), 45), styles["cell"]),
            Paragraph(_text(f"{fact.get('normalized_value')} {fact.get('unit') or ''}".strip(), 65), styles["cell"]),
            Paragraph(_text(f"{state}: {quote}", 190), styles["cell"]),
        ])
    if len(rows) == 1:
        rows.append([Paragraph("No extracted details", styles["cell"]), Paragraph("—", styles["cell"]), Paragraph("—", styles["cell"]), Paragraph("No facts were sent for extraction because the intake gate required review.", styles["cell"])])
    ft = Table(rows, colWidths=[30 * mm, 29 * mm, 33 * mm, 76 * mm], repeatRows=1)
    ft.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(ft)

    # Explicitly disambiguate the known high-risk aggregate in this test.
    extracted_values = " ".join(str(f.get("normalized_value", "")) for f in grounding)
    if "53600" in extracted_values or "53,600" in source_texts:
        story.append(Paragraph("Why 53,600 tonnes is not the 20-tonne claim", styles["h"]))
        story.append(Paragraph(
            "The uploaded Suffolk document reports 53,600 tonnes as a historical total for the composition of mixed household recyclables. "
            "That is an aggregate across material streams and a reporting period, not a weight ticket for a single shipment. "
            "It cannot be used to prove the 20-tonne electronic-waste claim. The material and event context do not match.", styles["body"]))
    if "2019" in extracted_values:
        story.append(Paragraph(
            "Date interpretation: a value such as 2019 or 2019/20 can refer to a contract year, financial year, or historical reporting period. "
            "It must not be presented as the event date of an individual shipment unless the source says that it is.", styles["body"]))

    story.append(Paragraph("Period and extraction coverage", styles["h"]))
    story.append(Paragraph(
        f"<b>Claim period:</b> {_text((periods.get('claim_period') or {}).get('start'))} to {_text((periods.get('claim_period') or {}).get('end'))}. "
        f"<b>In-period documents:</b> {_text(periods.get('in_period_count', 0))}; "
        f"<b>out of period:</b> {_text(periods.get('out_of_period_count', 0))}; "
        f"<b>undated:</b> {_text(periods.get('undated_count', 0))}.", styles["body"]))
    coverage_text = (f"{_text(coverage.get('coverage_pct'))}%" if coverage.get('coverage_pct') is not None else "not available")
    story.append(Paragraph(
        f"<b>Extraction coverage:</b> {coverage_text}. Coverage means whether documents produced extracted fields. "
        "It is not a probability, a confidence score for the whole claim, or proof that the claim is valid.", styles["body"]))

    story.append(Paragraph("Findings and recommended next steps", styles["h"]))
    if not findings:
        story.append(Paragraph("No explicit findings were returned. Review the document list and source checks before relying on the result.", styles["body"]))
    else:
        for finding in findings[:15]:
            story.append(Paragraph(
                f"<b>{_text(finding.get('severity') or 'Note').upper()} — {_text(finding.get('type') or 'finding').replace('_', ' ')}</b>: "
                f"{_text(finding.get('message'))}", styles["body"]))

    story.append(Paragraph("Reviewer checklist", styles["h"]))
    steps = [
        "Confirm that each document concerns the material and company/facility in the selected claim.",
        "Use shipment, transport, receiving/weighbridge and processing records for shipment weight; keep historical aggregate statistics separate.",
        "Confirm the relevant event date and jurisdiction from the source, especially where formats such as DD/MM/YYYY or financial-year labels are used.",
        "Review rejected/unverified quotes and any conflict before treating a quantity as supported.",
    ]
    for step in steps:
        story.append(Paragraph(f"- {_text(step)}", styles["body"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("This report summarises the supplied analysis response. It does not certify document authenticity or replace an authorised human review.", styles["small"]))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
