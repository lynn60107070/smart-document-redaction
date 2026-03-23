# Smart Document Redaction

## Overview
Smart Document Redaction is a system that automatically detects sensitive entities in documents using AI (NER) and redacts them from PDF files.

It combines:
- AI-based Named Entity Recognition (NER)
- PDF text extraction and processing
- Coordinate mapping for accurate redaction

---

## Document Processing Workflow

This layer converts PDFs into text, maps NER offsets to PDF coordinates, and applies redactions.

### 1. Extract text
- File: `document_processing/text_extractor.py`
- Function: `extract_text(pdf_file)`
- Returns: `ExtractedDocument` containing:
  - Full text
  - Per-page text
  - Word bounding boxes

### 2. Run NER (AI layer)
- Input: `ExtractedDocument.text`
- Output: entity spans with offsets

### 3. Map entities to boxes
- File: `document_processing/entity_mapper.py`
- Function: `map_entities(extracted, entities)`
- Output: page-level bounding boxes for each entity

### 4. Apply redactions
- File: `document_processing/redaction_engine.py`
- Function: `redact_pdf(pdf_file, entities, output_path=None)`
- Returns:
  - Redacted PDF as bytes OR
  - Saved file path

---

## Public API (Document Processing)

- `extract_text(file)` → `ExtractedDocument`
- `redact_pdf(file, entities, output_path=None)` → `bytes | str`

---

## Entity Input Contract

Entities must align exactly with `ExtractedDocument.text`:

```json
[
  {
    "text": "John Doe",
    "start": 120,
    "end": 128,
    "label": "PERSON"
  }
]