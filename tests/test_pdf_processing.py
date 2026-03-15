import fitz

from document_processing.entity_mapper import map_entities
from document_processing.pdf_utils import PAGE_SEPARATOR
from document_processing.text_extractor import extract_text


def _create_sample_pdf(path):
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "John Doe")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Jane Roe")
    doc.save(path)
    doc.close()


def test_extract_text_and_mapping(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    _create_sample_pdf(str(pdf_path))

    extracted = extract_text(str(pdf_path))
    assert "John Doe" in extracted.text
    assert "Jane Roe" in extracted.text
    assert PAGE_SEPARATOR in extracted.text

    john_start = extracted.text.index("John Doe")
    jane_start = extracted.text.index("Jane Roe")

    entities = [
        {"text": "John Doe", "start": john_start, "end": john_start + len("John Doe"), "label": "PERSON"},
        {"text": "Jane Roe", "start": jane_start, "end": jane_start + len("Jane Roe"), "label": "PERSON"},
    ]

    mapped = map_entities(extracted, entities)
    pages = {item["page"] for item in mapped}
    assert pages == {0, 1}
