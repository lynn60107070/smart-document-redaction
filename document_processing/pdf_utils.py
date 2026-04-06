"""
Shared PDF primitives: open documents, typed extract structures, and rectangle
merge helpers used by ``text_extractor`` and ``entity_mapper``.

Falls back to local defaults if ``utils.constants`` is not importable (e.g. odd
``PYTHONPATH`` when running a single script).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, Union, IO

import fitz  # PyMuPDF

try:
    from utils.constants import (
        PAGE_SEPARATOR,
        LINE_MERGE_TOLERANCE,
        LINE_MERGE_X_GAP,
        REDACTION_Y_INSET,
    )
except Exception:
    PAGE_SEPARATOR = "\n\n"
    LINE_MERGE_TOLERANCE = 2.0
    LINE_MERGE_X_GAP = 2.0
    REDACTION_Y_INSET = 1.25


RectTuple = Tuple[float, float, float, float]


@dataclass(frozen=True)
class WordBox:
    """A word with its bounding box and global character offsets."""

    text: str
    start: int
    end: int
    bbox: RectTuple
    page_index: int


@dataclass(frozen=True)
class ExtractedPage:
    """Structured content for a single PDF page."""

    page_index: int
    text: str
    char_offset_start: int
    words: List[WordBox]


@dataclass(frozen=True)
class ExtractedDocument:
    """Full extracted document content and indexes for mapping offsets."""

    text: str
    pages: List[ExtractedPage]
    word_index: List[WordBox]


def open_pdf(pdf_file: Union[str, bytes, IO[bytes]]) -> fitz.Document:
    """Open a PDF from a path, bytes, or a binary file-like object."""

    if isinstance(pdf_file, (str, bytes, bytearray)):
        if isinstance(pdf_file, str):
            return fitz.open(pdf_file)
        return fitz.open(stream=bytes(pdf_file), filetype="pdf")

    data = pdf_file.read()
    return fitz.open(stream=data, filetype="pdf")


def save_pdf(doc: fitz.Document, output_path: str) -> str:
    """Save a PyMuPDF document to disk and return the output path."""

    doc.save(output_path)
    return output_path


def is_same_line(rect_a: RectTuple, rect_b: RectTuple, y_tolerance: float) -> bool:
    """Return True if two rectangles are on the same line within tolerance."""

    y0_a, y1_a = rect_a[1], rect_a[3]
    y0_b, y1_b = rect_b[1], rect_b[3]
    return abs(y0_a - y0_b) <= y_tolerance and abs(y1_a - y1_b) <= y_tolerance


def merge_rects(
    rects: Sequence[RectTuple],
    y_tolerance: float = LINE_MERGE_TOLERANCE,
    x_gap: float = LINE_MERGE_X_GAP,
) -> List[RectTuple]:
    """Merge rectangles on the same line if they overlap or are close.

    Horizontally adjacent boxes are unioned on x. Vertically, word boxes from
    PyMuPDF are often taller than the ink; taking the **intersection** of y
    ranges while merging keeps the redaction band tight so it does not cover
    neighbouring lines. If intervals do not overlap, y falls back to union.
    """

    if not rects:
        return []

    sorted_rects = sorted(rects, key=lambda r: (r[1], r[0]))
    merged: List[RectTuple] = []

    def _merge_y_union(a: RectTuple, b: RectTuple) -> Tuple[float, float]:
        return (min(a[1], b[1]), max(a[3], b[3]))

    def _merge_y_intersect(a: RectTuple, b: RectTuple) -> Tuple[float, float] | None:
        y0 = max(a[1], b[1])
        y1 = min(a[3], b[3])
        if y1 > y0:
            return (y0, y1)
        return None

    current = list(sorted_rects[0])
    for rect in sorted_rects[1:]:
        if is_same_line(tuple(current), rect, y_tolerance) and rect[0] <= current[2] + x_gap:
            current[0] = min(current[0], rect[0])
            current[2] = max(current[2], rect[2])
            iy = _merge_y_intersect(tuple(current), rect)
            if iy is not None:
                current[1], current[3] = iy
            else:
                current[1], current[3] = _merge_y_union(tuple(current), rect)
        else:
            merged.append(tuple(current))  # type: ignore[arg-type]
            current = list(rect)

    merged.append(tuple(current))  # type: ignore[arg-type]
    return merged


def inset_redaction_rect_y(
    rect: RectTuple,
    inset: float = REDACTION_Y_INSET,
    min_height: float = 1.0,
) -> RectTuple:
    """Narrow a redaction box vertically (PDF space, y grows downward)."""

    if inset <= 0:
        return rect
    x0, y0, x1, y1 = rect
    ny0 = y0 + inset
    ny1 = y1 - inset
    if ny1 - ny0 >= min_height:
        return (x0, ny0, x1, ny1)
    mid = 0.5 * (y0 + y1)
    half = max(min_height * 0.5, (y1 - y0) * 0.5 * 0.35)
    return (x0, mid - half, x1, mid + half)
