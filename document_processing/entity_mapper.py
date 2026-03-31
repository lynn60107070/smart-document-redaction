"""
Bridge from NER character offsets to PDF coordinates.

Each ``WordBox`` in ``extracted.word_index`` overlaps an entity ``[start,end)``
inclusive-exclusive on the global string; hits are merged per page with
``merge_rects`` so multi-word entities become one redaction rectangle.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from .pdf_utils import ExtractedDocument, RectTuple, merge_rects


def map_entities(
    extracted: ExtractedDocument,
    entities: Sequence[Dict[str, object]],
    y_tolerance: float = 2.0,
    x_gap: float = 2.0,
) -> List[Dict[str, object]]:
    """
    Map NER entity offsets to PDF bounding boxes.

    Args:
        extracted: ExtractedDocument from text_extractor.
        entities: list of dicts with keys: text, start, end, label.
        y_tolerance: max vertical difference for same-line merging.
        x_gap: max horizontal gap for merging adjacent rects.

    Returns:
        List of mapped entity dicts:
        {page: int, rect: (x0,y0,x1,y1), label: str, text: str}
    """

    mapped: List[Dict[str, object]] = []
    if not entities:
        return mapped

    for ent in entities:
        try:
            start = int(ent["start"])  # type: ignore[index]
            end = int(ent["end"])  # type: ignore[index]
            label = str(ent.get("label", ""))
            text = str(ent.get("text", ""))
        except Exception:
            continue

        hits_by_page: Dict[int, List[RectTuple]] = {}
        for word in extracted.word_index:
            if word.start < end and word.end > start:
                hits_by_page.setdefault(word.page_index, []).append(word.bbox)

        for page_index, rects in hits_by_page.items():
            for rect in merge_rects(rects, y_tolerance=y_tolerance, x_gap=x_gap):
                mapped.append(
                    {
                        "page": page_index,
                        "rect": rect,
                        "label": label,
                        "text": text,
                    }
                )

    return mapped
