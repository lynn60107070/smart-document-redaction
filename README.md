# Smart Document Redaction

End-to-end pipeline to **detect sensitive entities** in PDFs (spaCy NER plus regex patterns), **map** spans to PDF coordinates, and **redact** selected regions. The product surface is a **Next.js** web app backed by a **FastAPI** server.

---

## What we identify and redact

Detection is **hybrid**: a **custom spaCy NER model** (`model/ner_model`) proposes spans, and **regular expressions** add structured identifiers. Overlapping spans are merged so one region is not double-counted (`ai_model/entity_detector.py`).

### Neural NER (model output)

The fine-tuned pipeline is trained for **named-entity–style categories** aligned with the project dataset, including:

- **PERSON** — people’s names  
- **ORGANIZATION** — companies, institutions, and similar groups  
- **LOCATION** — places (countries, cities, regions, etc.)  
- **DATE** / **TIME** — calendar and clock-style expressions (as tagged in training)

Exact behavior depends on what the model predicts on your PDF text; labels are normalized to uppercase in code.

### Rule-based patterns (always run on extracted text)

These are matched **in addition** to NER:

- **EMAIL** — email addresses  
- **PHONE** — long digit sequences (phone-like numbers; may match other numeric strings)  
- **CREDIT_CARD** — 13–16 consecutive digits (card-like; can false-positive on other numbers)  
- **ID** — 6–12 character alphanumeric tokens (generic “ID-like” strings; can false-positive on codes, order IDs, etc.)

The detector **drops** NER spans whose text is only digits, and ignores trivial spans **email** and **contact** so generic words are not treated as entities.

**Redaction** applies to whatever entities the UI (or API client) leaves **enabled** after review — you can turn detections off before exporting the PDF.

---

## What’s in the stack

| Layer | Technology |
|--------|------------|
| Web UI | Next.js 16, React 18, TypeScript |
| API | FastAPI, Uvicorn, Pydantic v2 |
| NLP | spaCy 3.7+ (custom `model/ner_model`), hybrid rules in `ai_model/entity_detector.py` |
| PDF | PyMuPDF (`fitz`) — extract text, word boxes, draw redactions |

---

## Prerequisites

- **Python** 3.10+ (3.12 is fine). Use a **virtual environment** (`.venv` / `venv` — see `.gitignore`).
- **Node.js** 18+ (for Next.js; LTS recommended).
- **npm** (comes with Node).
- A trained spaCy pipeline at **`model/ner_model/`** (included in a full checkout). The API loads it via `ai_model/ner_model.py` → `load_ner_model()`.

---

## First-time setup (Python)

From the **repository root** (the folder that contains `backend_api/`, `web/`, `requirements.txt`):

```bash
python -m venv .venv
```

Activate the environment:

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

Install dependencies:

```bash
pip install -r requirements.txt
```

### spaCy baseline model (training only)

If you run **`ai_model/train_model.py`** with the default `--pretrained en_core_web_lg`, install the weights after the step above (large download, ~800 MB):

```bash
python -m spacy download en_core_web_lg
```

Inference for the web API uses your **on-disk** `model/ner_model` bundle, not this download, unless you point code at another path.

---

## First-time setup (web)

```bash
cd web
npm i
```

---

## How to run (development)

1. **Activate your Python virtual environment** (see [First-time setup (Python)](#first-time-setup-python)) so `python` and `pip` point at the project venv.
2. **Use two terminals** — backend and frontend run together.

Stay in the activated venv for the backend terminal.

### Terminal 1 — backend (FastAPI)

From the **repository root**:

```bash
python -m uvicorn backend_api.main:app --reload
```

Default URL: `http://127.0.0.1:8000`

Interactive docs: `http://127.0.0.1:8000/docs`

### Terminal 2 — web app (Next.js)

```bash
cd web
npm i
npm run dev
```

Follow the URL printed in the terminal (typically `http://localhost:3000`).

### Pointing the frontend at a different API URL

The browser calls the API using `web/lib/api.ts`. Override the base URL with an environment variable when building or running Next.js:

```bash
set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

On macOS/Linux use `export` instead of `set`.

**Note:** The analyze response currently embeds absolute `imageUrl` values for page previews using `http://127.0.0.1:8000` in `backend_api/main.py`. If you expose the API on another host or port, you may need to align that logic or use a proxy so preview images still load.

---

## Project layout

High-level map of the repo (binary / generated artifacts omitted for clarity):

```text
smart-document-redaction/
├── README.md
├── requirements.txt
├── backend_api/              # FastAPI app (HTTP API, temp PDF store)
│   ├── main.py               # Routes: /api/health, analyze, redact, map, downloads, page images
│   ├── service.py            # analyze_pdf, redactions, thumbnails (uses NER + document_processing)
│   └── store.py              # In-memory/temp storage for uploads and redacted outputs
├── web/                      # Next.js frontend
│   ├── app/                  # App Router pages (landing, review flow)
│   ├── components/
│   └── lib/api.ts            # Fetch helpers; NEXT_PUBLIC_API_BASE_URL
├── document_processing/      # PDF pipeline (no HTTP)
│   ├── text_extractor.py     # extract_text → full text + per-page word boxes
│   ├── entity_mapper.py      # Map NER spans to PDF rectangles
│   ├── redaction_engine.py   # redact_pdf
│   └── pdf_utils.py          # PyMuPDF helpers
├── ai_model/
│   ├── ner_model.py          # load_ner_model(), Pydantic v2 schema rebuild
│   ├── entity_detector.py    # NER + regex merge, CLI: python entity_detector.py -t "..."
│   ├── preprocess_dataset.py # CSV → cleaned data + DocBin (data/processed/)
│   ├── train_model.py        # Fine-tune from DocBin → model/ner_model/model-best (default)
│   └── evaluation.py         # Metrics, plots, reports under artifacts dir
├── model/
│   └── ner_model/            # Serialized spaCy pipeline used at inference (when present)
├── data/
│   ├── raw/                  # e.g. NER_raw.csv
│   └── processed/            # JSON/JSONL/CSV/DocBin from preprocessing
├── notebooks/                # EDA, training experiments (Jupyter)
├── tests/                    # pytest: API, PDF, redaction, NER
├── utils/
│   └── constants.py          # Shared constants (e.g. page separator)
└── app/designs/              # Static HTML design references (not the Next app)
```

---

## HTTP API (summary)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness check |
| POST | `/api/analyze` | Upload PDF → text, entities, mapped boxes, page metadata |
| POST | `/api/redact` | Apply redaction for enabled entities → download token / URLs |
| POST | `/api/map` | Re-map a custom entity list to PDF boxes (preview flow) |
| GET | `/api/download/{token}` | Download redacted PDF |
| GET | `/api/documents/{id}/pages/{i}/image` | Page PNG for original upload |
| GET | `/api/outputs/{token}/pages/{i}/image` | Page PNG for redacted output |

Request/response shapes match the Pydantic models in `backend_api/main.py` and the TypeScript types under `web/lib/`.

---

## Document processing workflow (Python)

1. **Extract text and geometry** — `document_processing/text_extractor.py` → `extract_text`.
2. **Detect entities** — `ai_model/entity_detector.py` → `detect_entities(nlp, text)` (spaCy spans + `REGEX_PATTERNS`).
3. **Map to PDF** — `document_processing/entity_mapper.py` → `map_entities`.
4. **Redact** — `document_processing/redaction_engine.py` → `redact_pdf`.

Entity dicts must match the **exact** character offsets in the extracted full-document string:

```json
{
  "text": "John Doe",
  "start": 120,
  "end": 128,
  "label": "PERSON"
}
```

---

## Data and training (optional)

1. **Preprocess** (from repo root; adjust paths if your raw CSV lives elsewhere):

   ```bash
   python ai_model/preprocess_dataset.py --help
   ```

   Typical outputs under `data/processed/`: `redaction_train.spacy` (DocBin), JSON/JSONL, cleaned CSVs.

2. **Download baseline** (once): `python -m spacy download en_core_web_lg`

3. **Train** (defaults use `data/processed/redaction_train.spacy` and write under `model/ner_model/`):

   ```bash
   python ai_model/train_model.py --help
   ```

   Use `--artifacts-dir` for curves, metrics, and figures. Point inference at the new bundle if you save outside `model/ner_model/`.

4. **Try detection on a sentence** (from `ai_model/` or with `PYTHONPATH` set to repo root):

   ```bash
   cd ai_model
   python entity_detector.py -t "Contact me at 555-1234567 or a@b.com"
   python entity_detector.py --demo
   ```

---

## Tests

From the **repository root**, with the venv active and dev dependencies installed:

```bash
python -m pytest
```

Useful subsets:

```bash
python -m pytest tests/test_api.py -v
python -m pytest tests/test_ner.py -v
```

`tests/conftest.py` adds the repo root to `sys.path` so imports like `backend_api` and `ai_model` resolve.

---

## Production-style runs

- **API:** `python -m uvicorn backend_api.main:app --host 0.0.0.0 --port 8000` (drop `--reload` in production).
- **Web:** `cd web && npm run build && npm start`

Configure TLS, secrets, and `NEXT_PUBLIC_API_BASE_URL` for your deployment topology.

---

## Troubleshooting

- **`spaCy` / `Pydantic` errors when loading the model** — Ensure `pip install -r requirements.txt` (spaCy ≥ 3.7, Pydantic v2). See `rebuild_spacy_pydantic_schemas()` in `ai_model/ner_model.py`.
- **`FileNotFoundError` for the model** — Confirm `model/ner_model` exists or pass a custom path where your code supports it.
- **CORS** — Development middleware allows all origins (`backend_api/main.py`). Tighten for production.
- **Empty or wrong redactions** — Offsets must refer to the same string as `extract_text` returns (including page separators). Mixed encodings or unusual PDFs can shift alignment.

---

## License / course use

This repository was developed as a **course project** for **DSAI4201 — Selected Topics in Data Science**, **Winter 2026**, at the **University of Doha for Science and Technology (UDST)**.
