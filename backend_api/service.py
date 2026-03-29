from __future__ import annotations

from functools import lru_cache
from typing import Any

import fitz

from ai_model.entity_detector import detect_entities
from ai_model.ner_model import load_ner_model
from document_processing.entity_mapper import map_entities
from document_processing.pdf_utils import open_pdf
from document_processing.redaction_engine import redact_pdf
from document_processing.text_extractor import extract_text


@lru_cache(maxsize=1)
def get_nlp():
    return load_ner_model()


def analyze_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    extracted = extract_text(pdf_bytes)
    entities = detect_entities(get_nlp(), extracted.text)
    mapped = map_entities(extracted, entities)
    mapped_entities = []
    for item in mapped:
        match = next(
            (
                entity
                for entity in entities
                if entity["label"] == item["label"] and entity["text"] == item["text"]
            ),
            None,
        )
        if match is None:
            continue
        mapped_entities.append(
            {
                "page": item["page"],
                "rect": list(item["rect"]),
                "label": item["label"],
                "text": item["text"],
                "start": match["start"],
                "end": match["end"],
            }
        )
    page_previews = []
    doc = open_pdf(pdf_bytes)
    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            rect = page.rect
            page_previews.append(
                {
                    "pageIndex": page_index,
                    "width": rect.width,
                    "height": rect.height,
                }
            )
    finally:
        doc.close()
    return {
        "text": extracted.text,
        "pageCount": len(extracted.pages),
        "entities": entities,
        "mappedEntities": mapped_entities,
        "pages": page_previews,
    }


def apply_redactions(pdf_bytes: bytes, entities: list[dict[str, Any]]) -> bytes:
    redacted = redact_pdf(pdf_bytes, entities)
    if isinstance(redacted, bytes):
        return redacted
    raise TypeError("Expected redacted PDF bytes")


def render_page_image(pdf_bytes: bytes, page_index: int, zoom: float = 1.4) -> bytes:
    doc = open_pdf(pdf_bytes)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise IndexError("Page index out of range.")
        page = doc.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pixmap.tobytes("png")
    finally:
        doc.close()
