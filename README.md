# Smart Document Redaction

**You can use this tool on PDF files and on pasted plain text**; the same NLP stack powers both. It **detects** candidate sensitive spans (custom spaCy NER + regex), lets you **review** them in the browser, then **redacts** only what you approve.

| | **PDF mode** | **Text mode** |
|---|----------------|---------------|
| **Input** | Upload a `.pdf` | Paste or type into the text box on the home page |
| **Preview** | Page images with highlight overlays; extracted text panel | Immediate **redacted** preview on the landing page |
| **Review** | Full **Review** screen (toggles, search, manual spans) | Optional: **Edit** opens the same **Review** tools as PDF |
| **Output** | Download a **redacted PDF** (PyMuPDF burn-in) | **Copy** redacted string (length-obscuring masks, not 1:1 character blocks) |

**Stack:** **Next.js** frontend · **FastAPI** API · **spaCy** NER · **PyMuPDF** for PDF text/geometry/redaction.

---
# Click to Watch The Demo Video
[![Demo Video](https://img.youtube.com/vi/vUTG6TlTZNg/maxresdefault.jpg)](https://youtu.be/vUTG6TlTZNg)


---

## Problem and motivation

Real documents (contracts, medical summaries, HR records, incident reports, and disclosure drafts) often need to be shared or published with **personally identifiable information (PII)**, financial identifiers, and other sensitive tokens removed. Doing this by hand is **slow**, **inconsistent**, and **easy to get wrong** (missed phone numbers, partial names, or “invisible” PDF text). Fully automated removal without review is risky: models **false-positive** on innocent phrases and **false-negative** on unusual formats.

The **well-defined problem** this project tackles is: given document text (from a PDF or from a paste buffer), propose candidate sensitive spans automatically, let a human confirm or correct them, then produce a redacted artifact, either a **downloadable PDF** or **copy-ready text**, suitable for downstream use.

---

## Context and objectives

**Context.** The system is built as a **course project** for **DSAI4201: Selected Topics in Data Science** (see [License / course use](#license--course-use)). It connects a **custom-trained NER model**, **document/PDF engineering**, and a **browser-based review UI** into one coherent workflow.

**Objectives.**

1. **Improve coverage** versus manual-only review by surfacing names, places, organizations, dates/times, and rule-based patterns (emails, phones, card-like digits, ID-like tokens).
2. **Preserve accountability** through **human-in-the-loop** review: users can disable false positives, add manual redactions from text selection or search, then export.
3. **Support two ingestion modes**: **PDFs** (structure, page previews, coordinate-accurate redaction) and **free text** (fast paste → automatic redacted preview → optional deep edit).
4. **Ground the solution in NLP**: statistical sequence labeling plus explicit patterns, not a single brittle keyword list.

---

## AI approach and justification

**Why NLP?** Sensitive content is **linguistically diverse** (names and organizations appear in many surface forms) and **partially regular** (emails, long digit runs). **Named entity recognition** learns from examples which token boundaries in context are likely sensitive; **regular expressions** reliably flag **structured** strings the model might skip or label inconsistently.

**What we run.** A **fine-tuned spaCy pipeline** (`model/ner_model`) performs **neural NER**; `ai_model/entity_detector.py` runs **regex passes** and **merges overlapping spans** so each region is handled once. That hybrid design **addresses the problem** by combining **context** (neural) with **precision on formats** (rules).

**How it connects to redaction.** Extracted text shares **one global character index** with the detector. For **PDFs**, spans are **mapped to word boxes** and burned in with PyMuPDF redaction annotations. For **pasted text**, redaction is applied **in the string domain**; masks use a **length-obscuring** filler so the width of the redaction does **not** equal the secret’s character count (reducing length-based inference). The **review UI** is the bridge between raw model output and **safe release**.

---

## Privacy and data handling

This project is **not** a cloud document vault: there is **no application database** storing your files or pasted content for analytics.

- **PDF workflow.** Uploaded PDFs and generated redacted PDFs are stored only under the OS **temp** tree via `backend_api/store.py`, keyed by short-lived IDs. Entries **expire after one hour** (`SESSION_TTL_SECONDS`) and are **deleted** on cleanup or access paths that prune expired items.
- **Text workflow.** Analyze/redact requests carry text in the **HTTP body**; the API does **not** persist pasted text to disk as part of the text endpoints’ design.
- **Browser.** The Next.js app may cache session state in **`localStorage`** until you clear it or start over; this is **client-side** only and under your control.

Treat this as **defense-in-depth for a dev/course deployment**: use **HTTPS** in real environments, tighten **CORS** beyond the permissive dev default, and follow your institution’s policies for **real** sensitive data. The architecture favors **ephemeral processing** over long-term retention.

---

## Web application features

End-to-end **features** available in the app (PDF path, text path, or both):

| Area | What you get |
|------|----------------|
| **Landing** | Toggle **PDF file** vs **Paste text**; **Get started** scrolls to the upload card; hero copy explains both workflows. |
| **PDF upload** | Drop zone → analyze → **Review** with **page thumbnails**, **zoom**, **page navigation**, **overlay** boxes for enabled entities, and **extracted text** (select text to pre-fill manual redaction). |
| **Paste text** | **Redact text** runs detection + automatic redaction → **redacted output** on the **same page** with **Copy** and **Edit**. |
| **Edit (text)** | Opens **Review** with the same **entity inspector** as PDFs: toggle detections, **search** the document string, **add manual** spans (offsets + label), **Confirm & redact**. |
| **Review (shared)** | Grouped entity cards, **enable/disable** per item, **select all** by group, **manual redaction** form, **safety score** summary, errors surfaced inline. |
| **Result** | **PDF**: download link + **redacted page preview** and summary counts. **Text**: **Copy redacted text** + read-only output + summary. **Start over** clears the session. |
| **API** | REST endpoints for health, analyze (PDF/text), redact (PDF/text), map, downloads, and page images, usable without the browser (see [HTTP API (summary)](#http-api-summary)). |

---

## Model performance (training notebook)

NER quality is measured the same way in **`notebooks/train_model.ipynb`** and **`ai_model/train_model.py`**: a **held-out validation split** from the project DocBin (`data/processed/redaction_train.spacy` or your configured path), using spaCy’s **`Scorer`** **entity-level** metrics (`ents_p`, `ents_r`, `ents_f`).

**Best validation epoch recorded in `notebooks/train_model.ipynb`** (final printed line of the training loop output):

| Metric | Value |
|--------|--------|
| **Precision** (`ents_p`) | **0.926** |
| **Recall** (`ents_r`) | **0.907** |
| **F1** (`ents_f`) | **0.916** |

**How to interpret this**

- Numbers reflect **neural NER on the validation split**, not an audit of whole PDFs in production.
- The live app also runs **regex rules** (email, phone-like, card-like, ID-like) and **merges** overlaps with NER, so end-user coverage can differ from NER-only scores.
- **Real PDFs** can shift tokenization/extraction vs. training sentences; treat metrics as a **sanity check** for the model, not a guarantee on every document.
- Re-training changes weights and splits; **re-run the notebook** or `train_model.py` and update this table if you change data or hyperparameters.

---

## What we identify and redact

Detection is **hybrid**: a **custom spaCy NER model** (`model/ner_model`) proposes spans, and **regular expressions** add structured identifiers. Overlapping spans are merged so one region is not double-counted (`ai_model/entity_detector.py`).

### Neural NER (model output)

The fine-tuned pipeline is trained for **named-entity–style categories** aligned with the project dataset, including:

- **PERSON**: people’s names  
- **ORGANIZATION**: companies, institutions, and similar groups  
- **LOCATION**: places (countries, cities, regions, etc.)  
- **DATE** / **TIME**: calendar and clock-style expressions (as tagged in training)

Exact behavior depends on what the model predicts on your PDF text; labels are normalized to uppercase in code.

### Rule-based patterns (always run on extracted text)

These are matched **in addition** to NER:

- **EMAIL**: email addresses  
- **PHONE**: long digit sequences (phone-like numbers; may match other numeric strings)  
- **CREDIT_CARD**: 13–16 consecutive digits (card-like; can false-positive on other numbers)  
- **ID**: 6–12 character alphanumeric tokens (generic “ID-like” strings; can false-positive on codes, order IDs, etc.)

The detector **drops** NER spans whose text is only digits, and ignores trivial spans **email** and **contact** so generic words are not treated as entities.

**Redaction** applies to whatever entities the UI (or API client) leaves **enabled** after review: you can turn detections off before exporting. **PDF** export applies true page redactions; **text** export replaces spans with **length-obscuring** block masks (see `backend_api/service.py`).

---

## What’s in the stack

| Layer | Technology |
|--------|------------|
| Web UI | Next.js 16, React 18, TypeScript |
| API | FastAPI, Uvicorn, Pydantic v2 |
| NLP | spaCy 3.7+ (custom `model/ner_model`), hybrid rules in `ai_model/entity_detector.py` |
| PDF | PyMuPDF (`fitz`): extract text, word boxes, draw redactions |

---

## Prerequisites

- **Python** 3.10+ (3.12 is fine). Use a **virtual environment** (`.venv` / `venv`: see `.gitignore`).
- **Node.js** 18+ (for Next.js; LTS recommended).
- **npm** (comes with Node).
- A trained spaCy pipeline at **`model/ner_model/`** (included in a full checkout). The API loads it via `ai_model/ner_model.py` → `load_ner_model()`.

---

## First-time setup (Python)

These commands match **steps 1–2** in [How to run (development)](#how-to-run-development) below. Run them from the **repository root** (the folder that contains `backend_api/`, `web/`, and `requirements.txt`):

```bash
cd path/to/smart-document-redaction
python -m venv .venv
```

Activate the environment:

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

Install dependencies (with the venv active):

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

## How to run (development)

Use **two terminals**. All paths are from the **repository root** unless noted.

### 1. Go to the repository root

```bash
cd path/to/smart-document-redaction
```

(Replace `path/to/smart-document-redaction` with your actual clone path, i.e. the directory that contains `backend_api/`, `web/`, and `requirements.txt`.)

### 2. One-time setup: virtual environment, Python deps, and frontend deps

Skip this block if you already created `.venv`, ran `pip install`, and ran `npm i` in `web/`.

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

2. **Activate** it (do this in every new terminal where you run Python commands):

   - **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
   - **macOS / Linux:** `source .venv/bin/activate`

3. Install Python packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Install frontend packages (**from repository root**):

   ```bash
   cd web
   npm i
   cd ..
   ```

### 3. Terminal 1: backend (FastAPI)

1. **Activate the venv** (see step 2 above) if it is not already active.
2. **Stay at the repository root** (not inside `web/`).
3. Start Uvicorn:

   ```bash
   python -m uvicorn backend_api.main:app --reload
   ```

- API: `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs`

### 4. Terminal 2: web app (Next.js)

```bash
cd web
npm run dev
```

- The first time (or after `package.json` changes), run **`npm i`** inside `web/` before `npm run dev` (see step 2).
- Open the URL printed in the terminal (typically `http://localhost:3000`).

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
│   ├── main.py               # Routes: /api/health, analyze, analyze-text, redact, redact-text, map, downloads, page images
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
| POST | `/api/analyze-text` | JSON body `{ "text": "..." }` → same shape as analyze (no PDF stored; `inputMode: "text"`) |
| POST | `/api/redact` | PDF: `documentId` + entities → redacted PDF token / download + preview URLs |
| POST | `/api/redact-text` | JSON: full `text` + entities → `{ redactedText, summary, ... }` (no PDF) |
| POST | `/api/map` | Re-map a custom entity list to PDF boxes (preview flow; PDF sessions only) |
| GET | `/api/download/{token}` | Download redacted PDF |
| GET | `/api/documents/{id}/pages/{i}/image` | Page PNG for original upload |
| GET | `/api/outputs/{token}/pages/{i}/image` | Page PNG for redacted output |

Request/response shapes match the Pydantic models in `backend_api/main.py` and the TypeScript types under `web/lib/`.

---

## Document processing workflow (Python)

**PDF path**

1. **Extract text and geometry**: `document_processing/text_extractor.py` → `extract_text`.
2. **Detect entities**: `ai_model/entity_detector.py` → `detect_entities(nlp, text)` (spaCy spans + `REGEX_PATTERNS`).
3. **Map to PDF**: `document_processing/entity_mapper.py` → `map_entities`.
4. **Redact**: `document_processing/redaction_engine.py` → `redact_pdf`.

**Plain-text path**

1. **Detect entities** on the pasted string: `backend_api/service.py` → `analyze_plain_text` (same `detect_entities`).
2. **Redact**: `apply_text_redactions` merges enabled spans and substitutes length-obscuring masks (no PDF geometry).

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

- **`spaCy` / `Pydantic` errors when loading the model**: Ensure `pip install -r requirements.txt` (spaCy ≥ 3.7, Pydantic v2). See `rebuild_spacy_pydantic_schemas()` in `ai_model/ner_model.py`.
- **`FileNotFoundError` for the model**: Confirm `model/ner_model` exists or pass a custom path where your code supports it.
- **CORS**: Development middleware allows all origins (`backend_api/main.py`). Tighten for production.
- **Empty or wrong redactions**: Offsets must refer to the same string as `extract_text` returns (including page separators). Mixed encodings or unusual PDFs can shift alignment.

---

## License / course use

This repository was developed as a **course project** for **DSAI4201: Selected Topics in Data Science**, **Winter 2026**, at the **University of Doha for Science and Technology (UDST)**.
