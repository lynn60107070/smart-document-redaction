from __future__ import annotations

import hashlib
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


def analyze_plain_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Text is empty.")
    entities = detect_entities(get_nlp(), text)
    return {
        "text": text,
        "pageCount": 1,
        "entities": entities,
        "mappedEntities": [],
        "pages": [],
    }


def length_obscuring_text_mask(ordinal: int, start: int, end: int) -> str:
    """
    Deterministic redaction filler whose length does not match the original span,
    so readers cannot infer secret length from the mask. Uses a hash of position
    only (not the redacted substring) so the original text is not mixed into the
    derivation.
    """
    digest = hashlib.blake2b(
        f"{ordinal}\0{start}\0{end}".encode("utf-8"),
        digest_size=32,
    ).digest()
    run_len = 7 + (digest[0] % 12)
    palette = ("█", "■", "▓", "░")
    return "".join(palette[digest[(j % 31) + 1] % 4] for j in range(run_len))


def apply_text_redactions(full_text: str, entities: list[dict[str, Any]]) -> str:
    """Replace enabled entity spans with length-obscuring block masks."""
    spans: list[tuple[int, int]] = []
    for entity in entities:
        if not entity.get("enabled", True):
            continue
        start = int(entity["start"])
        end = int(entity["end"])
        if start < 0 or end > len(full_text) or end <= start:
            continue
        spans.append((start, end))
    if not spans:
        return full_text
    spans.sort(key=lambda s: s[0])
    merged: list[list[int]] = []
    for s, e in spans:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    parts: list[str] = []
    last = 0
    for i, (s, e) in enumerate(merged):
        parts.append(full_text[last:s])
        parts.append(length_obscuring_text_mask(i, s, e))
        last = e
    parts.append(full_text[last:])
    return "".join(parts)


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
