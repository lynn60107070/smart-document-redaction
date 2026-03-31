"""Shared literals for PDF text layout and box merging (imported by ``document_processing``)."""

# Inserted between pages in ``text_extractor``; must stay stable for offset-based NER.
PAGE_SEPARATOR = "\n\n"

# ``entity_mapper.merge_rects`` / pdf_utils: merge word boxes on the same line if this close (PDF units).
LINE_MERGE_TOLERANCE = 2.0
LINE_MERGE_X_GAP = 2.0
