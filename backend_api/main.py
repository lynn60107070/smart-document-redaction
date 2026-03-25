from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .service import analyze_pdf, apply_redactions, render_page_image
from .store import TempDocumentStore


class EntityPayload(BaseModel):
    text: str
    label: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    enabled: bool = True
    source: Literal["model", "manual"]


class RedactRequest(BaseModel):
    documentId: str
    entities: list[EntityPayload]


class MapRequest(BaseModel):
    documentId: str
    entities: list[EntityPayload]


app = FastAPI(title="Smart Redaction API")
store = TempDocumentStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validated_pdf_name(filename: str | None) -> str:
    name = filename or "document.pdf"
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    return Path(name).name


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, object]:
    filename = _validated_pdf_name(file.filename)
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    try:
        analysis = analyze_pdf(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to analyze PDF: {exc}") from exc

    stored = store.save_document(filename, pdf_bytes)
    entities = [
        {
            **entity,
            "enabled": True,
            "source": "model",
        }
        for entity in analysis["entities"]
    ]
    return {
        "documentId": stored.document_id,
        "filename": stored.filename,
        "text": analysis["text"],
        "pageCount": analysis["pageCount"],
        "entities": entities,
        "mappedEntities": [
            {
                **entity,
                "enabled": True,
                "source": "model",
            }
            for entity in analysis["mappedEntities"]
        ],
        "pages": [
            {
                **page,
                "imageUrl": f"http://127.0.0.1:8000/api/documents/{stored.document_id}/pages/{page['pageIndex']}/image",
            }
            for page in analysis["pages"]
        ],
    }


@app.post("/api/redact")
def redact(request: RedactRequest) -> dict[str, object]:
    stored = store.get_document(request.documentId)
    if stored is None:
        raise HTTPException(status_code=404, detail="Unknown or expired document.")

    final_entities = [
        {
            "text": entity.text,
            "label": entity.label,
            "start": entity.start,
            "end": entity.end,
        }
        for entity in request.entities
        if entity.enabled
    ]

    try:
        redacted_bytes = apply_redactions(stored.pdf_path.read_bytes(), final_entities)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to redact PDF: {exc}") from exc

    output_name = f"redacted_{stored.filename}"
    output = store.save_output(output_name, redacted_bytes)

    summary: dict[str, int] = {}
    for entity in request.entities:
        if entity.enabled:
            summary[entity.label] = summary.get(entity.label, 0) + 1

    return {
        "filename": output.filename,
        "outputToken": output.token,
        "downloadUrl": f"http://127.0.0.1:8000/api/download/{output.token}",
        "previewBaseUrl": f"http://127.0.0.1:8000/api/outputs/{output.token}/pages",
        "entityCount": sum(summary.values()),
        "summary": summary,
    }


@app.post("/api/map")
def map_entities_for_preview(request: MapRequest) -> dict[str, object]:
    stored = store.get_document(request.documentId)
    if stored is None:
        raise HTTPException(status_code=404, detail="Unknown or expired document.")

    try:
        analysis = analyze_pdf(stored.pdf_path.read_bytes())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to map entities: {exc}") from exc

    requested = [
        {
            "text": entity.text,
            "label": entity.label,
            "start": entity.start,
            "end": entity.end,
            "enabled": entity.enabled,
            "source": entity.source,
        }
        for entity in request.entities
    ]

    extracted_text = analysis["text"]
    from document_processing.text_extractor import extract_text  # local import to avoid broad churn
    from document_processing.entity_mapper import map_entities

    extracted = extract_text(stored.pdf_path.read_bytes())
    mapped = map_entities(
        extracted,
        [
            {
                "text": entity["text"],
                "label": entity["label"],
                "start": entity["start"],
                "end": entity["end"],
            }
            for entity in requested
        ],
    )

    mapped_entities = []
    for item in mapped:
        match = next(
            (
                entity
                for entity in requested
                if entity["label"] == item["label"]
                and entity["text"] == item["text"]
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
                "enabled": match["enabled"],
                "source": match["source"],
            }
        )

    return {"mappedEntities": mapped_entities, "text": extracted_text}


@app.get("/api/download/{token}")
def download(token: str) -> FileResponse:
    output = store.get_output(token)
    if output is None:
        raise HTTPException(status_code=404, detail="Unknown or expired download.")
    return FileResponse(
        output.pdf_path,
        media_type="application/pdf",
        filename=output.filename,
    )


@app.get("/api/documents/{document_id}/pages/{page_index}/image")
def page_image(document_id: str, page_index: int) -> Response:
    stored = store.get_document(document_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Unknown or expired document.")
    try:
        image = render_page_image(stored.pdf_path.read_bytes(), page_index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render page image: {exc}") from exc
    return Response(content=image, media_type="image/png")


@app.get("/api/outputs/{token}/pages/{page_index}/image")
def output_page_image(token: str, page_index: int) -> Response:
    output = store.get_output(token)
    if output is None:
        raise HTTPException(status_code=404, detail="Unknown or expired output.")
    try:
        image = render_page_image(output.pdf_path.read_bytes(), page_index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to render output page image: {exc}") from exc
    return Response(content=image, media_type="image/png")
