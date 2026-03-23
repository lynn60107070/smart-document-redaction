import fitz

from document_processing.redaction_engine import redact_pdf
from document_processing.text_extractor import extract_text

def _create_sample_pdf(path):
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "John Doe")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Jane Roe")
    doc.save(path)
    doc.close()


def test_redaction_removes_text(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _create_sample_pdf(str(pdf_path))

    original = extract_text(str(pdf_path))
    john_start = original.text.index("John Doe")
    entities = [
        {"text": "John Doe", "start": john_start, "end": john_start + len("John Doe"), "label": "PERSON"}
    ]

    redacted_bytes = redact_pdf(str(pdf_path), entities)
    redacted = extract_text(redacted_bytes)

    assert "John Doe" not in redacted.text
    assert "Jane Roe" in redacted.text
