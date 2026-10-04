from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .models import Artifact


def extract_pdf_source(
    path: str | Path,
) -> dict[str, Any]:
    """
    Extract page-level text from a PDF.

    Returns:
        {
            "page_count": int,
            "pages": [
                {
                    "page": 1,
                    "text": "..."
                }
            ],
            "full_text": "..."
        }
    """

    pdf_path = Path(path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Evidence file not found: {pdf_path}"
        )

    reader = PdfReader(str(pdf_path))

    pages: list[dict[str, Any]] = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        text = page.extract_text() or ""

        pages.append(
            {
                "page": page_number,
                "text": text,
            }
        )

    full_text = "\n\n".join(
        page["text"]
        for page in pages
    )

    return {
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
    }


def attach_pdf_source(
    artifact: Artifact,
) -> Artifact:
    """
    Read the actual PDF associated with an Artifact and attach
    page-level source text to artifact.metadata.

    Artifact.text becomes the extracted PDF text so the rest of the
    pipeline works against the actual source rather than demo fixture text.
    """

    if not artifact.local_path:
        return artifact

    source = extract_pdf_source(
        artifact.local_path
    )

    artifact.text = source["full_text"]

    artifact.metadata["page_count"] = (
        source["page_count"]
    )

    artifact.metadata["source_pages"] = (
        source["pages"]
    )

    return artifact
    