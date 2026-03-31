"""
Burn redaction annotations into a PDF using PyMuPDF.

Spans are re-mapped with ``map_entities`` so coordinates stay consistent with
``text_extractor`` output; only pages touched by at least one box get
``apply_redactions`` (per-page in loop).
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Union, IO

import fitz  # PyMuPDF

from .entity_mapper import map_entities
from .pdf_utils import open_pdf
from .text_extractor import extract_text


def redact_pdf(
    pdf_file: Union[str, bytes, IO[bytes]],
    entities: Sequence[Dict[str, object]],
    output_path: str | None = None,
) -> Union[bytes, str]:
    """
    Apply redactions to a PDF based on NER entity offsets.

    Args:
        pdf_file: PDF path, bytes, or binary file-like object.
        entities: list of dicts with keys: text, start, end, label.
        output_path: optional path to save the redacted PDF.

    Returns:
        If output_path is provided, returns that path.
        Otherwise returns the redacted PDF as bytes.
    """

    if isinstance(pdf_file, (str, bytes, bytearray)):
        pdf_source: Union[str, bytes] = pdf_file  # type: ignore[assignment]
    else:
        pdf_source = pdf_file.read()

    extracted = extract_text(pdf_source)
    mapped = map_entities(extracted, entities)

    doc = open_pdf(pdf_source)
    try:
        pages_to_apply: set[int] = set()
        for item in mapped:
            page_index = int(item["page"])  # type: ignore[index]
            rect = fitz.Rect(item["rect"])  # type: ignore[index]
            page = doc.load_page(page_index)
            annot = page.add_redact_annot(rect, fill=(0, 0, 0))
            if annot is not None:
                annot.update(fill_color=(0, 0, 0))
            pages_to_apply.add(page_index)

        for page_index in sorted(pages_to_apply):
            page = doc.load_page(page_index)
            page.apply_redactions()

        if output_path:
            doc.save(output_path)
            return output_path

        try:
            return doc.tobytes()
        except Exception:
            return doc.write()
    finally:
        doc.close()
