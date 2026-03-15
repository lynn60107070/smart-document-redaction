# Smart Document Redaction

Note: Add the rest of the sections' workflows as you gys work on it.explain the tests you have currrentl

## Document Processing Workflow

This layer converts PDFs into text, maps NER offsets to PDF coordinates, and applies redactions.

1. Extract text
   - `document_processing/text_extractor.py`
   - `extract_text(pdf_file)` returns an `ExtractedDocument` with full text, per-page text, and word boxes.
2. Run NER (AI layer)
   - NER consumes `ExtractedDocument.text` and returns entity offsets.
3. Map entities to boxes
   - `document_processing/entity_mapper.py`
   - `map_entities(extracted, entities)` returns page‑level bounding boxes.
4. Apply redactions
   - `document_processing/redaction_engine.py`
   - `redact_pdf(pdf_file, entities, output_path=None)` returns redacted PDF bytes or a saved path.

### Public API (Document Processing)

- `extract_text(file)` → `ExtractedDocument`
- `redact_pdf(file, entities, output_path=None)` → `bytes | str`

### Entity Input Contract

Entities must be based on the exact `ExtractedDocument.text` output:

```
[
  {"text": "John Doe", "start": 120, "end": 128, "label": "PERSON"}
]
```
