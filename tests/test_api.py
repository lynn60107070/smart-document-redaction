from __future__ import annotations

import fitz
from fastapi.testclient import TestClient

from backend_api import main as api_main
from backend_api.main import app


client = TestClient(app)


def _create_sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "John Doe")
    data = doc.tobytes()
    doc.close()
    return data


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_rejects_non_pdf():
    response = client.post(
        "/api/analyze",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_download_missing_token():
    response = client.get("/api/download/missing")
    assert response.status_code == 404


def test_analyze_and_redact_flow(monkeypatch):
    def fake_analyze_pdf(pdf_bytes: bytes):
        return {
            "text": "John Doe",
            "pageCount": 1,
            "entities": [
                {
                    "text": "John Doe",
                    "label": "PERSON",
                    "start": 0,
                    "end": 8,
                }
            ],
            "mappedEntities": [
                {
                    "page": 0,
                    "rect": [72.0, 60.0, 110.0, 75.0],
                    "label": "PERSON",
                    "text": "John Doe",
                    "start": 0,
                    "end": 8,
                }
            ],
            "pages": [
                {
                    "pageIndex": 0,
                    "width": 595.0,
                    "height": 842.0,
                }
            ],
        }

    monkeypatch.setattr(api_main, "analyze_pdf", fake_analyze_pdf)

    analyze_response = client.post(
        "/api/analyze",
        files={"file": ("sample.pdf", _create_sample_pdf_bytes(), "application/pdf")},
    )
    assert analyze_response.status_code == 200
    analyze_payload = analyze_response.json()
    assert analyze_payload["filename"] == "sample.pdf"
    assert analyze_payload["entities"][0]["enabled"] is True
    assert analyze_payload["entities"][0]["source"] == "model"
    assert analyze_payload["mappedEntities"][0]["page"] == 0
    assert analyze_payload["pages"][0]["pageIndex"] == 0

    redact_response = client.post(
        "/api/redact",
        json={
            "documentId": analyze_payload["documentId"],
            "entities": analyze_payload["entities"],
        },
    )
    assert redact_response.status_code == 200
    redact_payload = redact_response.json()
    assert redact_payload["entityCount"] == 1
    assert "/api/download/" in redact_payload["downloadUrl"]

    download_path = redact_payload["downloadUrl"].replace("http://127.0.0.1:8000", "")
    download_response = client.get(download_path)
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/pdf"


def test_redact_rejects_unknown_document():
    response = client.post(
        "/api/redact",
        json={
            "documentId": "missing",
            "entities": [],
        },
    )
    assert response.status_code == 404
