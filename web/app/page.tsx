"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ChangeEvent } from "react";

import { LoadingScreen } from "../components/loading-screen";
import { analyzePdf, analyzeText, redactText } from "../lib/api";
import type { AnalyzeResponse, InputMode } from "../lib/types";
import { useSession } from "../lib/session";

const MIN_LOADING_MS = 1100;

type TextQuickPreview = {
  analysis: AnalyzeResponse;
  redactedText: string;
  sourceSnapshot: string;
};

export default function Home() {
  const router = useRouter();
  const { clearSession, setAnalysis } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>("pdf");
  const [pastedText, setPastedText] = useState("");
  const [textQuickPreview, setTextQuickPreview] = useState<TextQuickPreview | null>(null);
  const [quickCopied, setQuickCopied] = useState(false);
  const [editNavigating, setEditNavigating] = useState(false);
  const previewAnchorRef = useRef<HTMLDivElement | null>(null);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    clearSession();
    setError(null);
    setIsAnalyzing(true);

    try {
      const [analysis] = await Promise.all([
        analyzePdf(file),
        new Promise((resolve) => window.setTimeout(resolve, MIN_LOADING_MS)),
      ]);
      setAnalysis(analysis);
      router.push("/review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze PDF.");
      setIsAnalyzing(false);
    } finally {
      event.target.value = "";
    }
  };

  const handleTextRedactQuick = async () => {
    if (!pastedText.trim()) {
      setError("Paste some text to redact.");
      return;
    }

    clearSession();
    setTextQuickPreview(null);
    setQuickCopied(false);
    setError(null);
    setIsAnalyzing(true);

    try {
      const [analysis] = await Promise.all([
        analyzeText(pastedText),
        new Promise((resolve) => window.setTimeout(resolve, MIN_LOADING_MS)),
      ]);
      const redactResult = await redactText(analysis.text, analysis.entities);
      setTextQuickPreview({
        analysis,
        redactedText: redactResult.redactedText,
        sourceSnapshot: pastedText,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to redact text.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  useEffect(() => {
    if (!textQuickPreview || isAnalyzing) {
      return;
    }
    previewAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [textQuickPreview, isAnalyzing]);

  const handleQuickCopy = async () => {
    if (!textQuickPreview) {
      return;
    }
    try {
      await navigator.clipboard.writeText(textQuickPreview.redactedText);
      setQuickCopied(true);
      window.setTimeout(() => setQuickCopied(false), 2200);
    } catch {
      setQuickCopied(false);
    }
  };

  const handleQuickEdit = async () => {
    if (!textQuickPreview) {
      return;
    }
    setError(null);
    if (pastedText === textQuickPreview.sourceSnapshot) {
      setAnalysis(textQuickPreview.analysis);
      router.push("/review");
      return;
    }
    setEditNavigating(true);
    try {
      const analysis = await analyzeText(pastedText);
      setAnalysis(analysis);
      router.push("/review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open editor.");
    } finally {
      setEditNavigating(false);
    }
  };

  const previewStale =
    textQuickPreview !== null && pastedText !== textQuickPreview.sourceSnapshot;

  return (
    <>
      {isAnalyzing ? (
        <LoadingScreen
          title="Analyzing document"
          subtitle={
            inputMode === "pdf"
              ? "Extracting PDF text, running entity detection, and preparing the review workspace."
              : "Detecting sensitive spans and building an automatic redacted preview you can copy or refine."
          }
          steps={
            inputMode === "pdf"
              ? [
                  "Reading PDF structure",
                  "Detecting sensitive entities",
                  "Preparing review preview",
                ]
              : [
                  "Scanning pasted text",
                  "Detecting sensitive entities",
                  "Applying automatic redactions",
                ]
          }
        />
      ) : null}
      <div className="site-shell">
        <header className="topbar">
          <div className="brand">Redactinator</div>
          <nav className="topnav">
            <a href="#lifecycle">How It Works</a>
            <a href="#trust">Project</a>
            <a className="button button-primary" href="#upload">
              Get started
            </a>
          </nav>
        </header>

        <main>
          <section className="hero">
            <div className="hero-copy">
              <p className="eyebrow">NLP Document Redaction</p>
              <h1>
                Redact sensitive
                <br />
                PDFs & text faster.
              </h1>
              <p className="hero-text">
                Redactinator combines Named Entity Recognition with PDF mapping and a
                paste-text workflow: drop a PDF for page-accurate redaction, or paste
                plain text for an instant redacted preview you can copy—then open
                <strong> Edit </strong>
                anytime to tune detections or add manual spans before final export.
              </p>
              <div className="hero-points">
                <span>PDF upload or paste text</span>
                <span>Instant text preview + full review</span>
              </div>
            </div>

            <div className="upload-panel" id="upload">
              <div className="upload-glow" />
              <div className="upload-card">
                <div
                  className="input-mode-tabs"
                  role="tablist"
                  aria-label="Input format"
                >
                  <button
                    type="button"
                    role="tab"
                    aria-selected={inputMode === "pdf"}
                    className={inputMode === "pdf" ? "is-active" : ""}
                    onClick={() => {
                      setInputMode("pdf");
                      setError(null);
                      setTextQuickPreview(null);
                      setQuickCopied(false);
                    }}
                  >
                    PDF file
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={inputMode === "text"}
                    className={inputMode === "text" ? "is-active" : ""}
                    onClick={() => {
                      setInputMode("text");
                      setError(null);
                    }}
                  >
                    Paste text
                  </button>
                </div>

                {inputMode === "pdf" ? (
                  <div className="upload-mode-body">
                    <input
                      id="pdf-upload"
                      className="upload-input"
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleFileChange}
                    />
                    <label className="upload-dropzone" htmlFor="pdf-upload">
                      <div className="upload-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none">
                          <path
                            d="M12 16V8"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                          />
                          <path
                            d="M8.5 11.5L12 8l3.5 3.5"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                          <path
                            d="M5 18.5h14"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                          />
                        </svg>
                      </div>
                      <h2>Drop your PDF here</h2>
                      <p>
                        Or switch to <strong>Paste text</strong> for instant copy-ready redaction—same
                        model, same review tools.
                      </p>
                      <span className="button button-primary">Select Document</span>
                      <small>PDF files up to 50MB</small>
                    </label>
                  </div>
                ) : (
                  <div className="upload-mode-body">
                    <div className="paste-text-panel paste-text-panel--hero">
                    <label className="paste-label" htmlFor="paste-text">
                      Document text
                    </label>
                    <textarea
                      id="paste-text"
                      className="paste-textarea"
                      value={pastedText}
                      onChange={(e) => setPastedText(e.target.value)}
                      placeholder="Paste or type the text you want to scan for sensitive entities..."
                      spellCheck={false}
                    />
                    <p className="paste-hint">
                      We redact everything the model detects by default. Copy the result if it
                      looks good, or use <strong>Edit</strong> to toggle items, add manual spans,
                      then export from the review screen.
                    </p>
                    <button
                      type="button"
                      className="button button-primary paste-analyze-btn"
                      onClick={handleTextRedactQuick}
                      disabled={isAnalyzing}
                    >
                      Redact text
                    </button>

                    {textQuickPreview ? (
                      <div
                        id="text-redacted-preview"
                        ref={previewAnchorRef}
                        className="paste-quick-preview"
                      >
                        <div className="paste-quick-preview-head">
                          <h3>Redacted output</h3>
                          <p className="paste-quick-preview-meta">
                            {textQuickPreview.analysis.entities.length} detection
                            {textQuickPreview.analysis.entities.length === 1 ? "" : "s"} — sensitive
                            spans replaced with mixed masks (length does not match the original)
                          </p>
                        </div>
                        {previewStale ? (
                          <p className="paste-stale-hint">
                            Your text changed since this preview. Click <strong>Redact text</strong>{" "}
                            to refresh the output. <strong>Edit</strong> will analyze what is in the
                            box now and open the full review workflow.
                          </p>
                        ) : null}
                        <pre className="paste-quick-output">{textQuickPreview.redactedText}</pre>
                        <div className="paste-quick-actions">
                          <button
                            type="button"
                            className="button button-primary"
                            onClick={handleQuickCopy}
                          >
                            {quickCopied ? "Copied" : "Copy"}
                          </button>
                          <button
                            type="button"
                            className="button button-outline"
                            onClick={() => void handleQuickEdit()}
                            disabled={editNavigating}
                          >
                            {editNavigating ? "Opening…" : "Edit"}
                          </button>
                        </div>
                      </div>
                    ) : null}
                    </div>
                  </div>
                )}
              </div>
              {isAnalyzing ? <p className="upload-status">Preparing review workspace...</p> : null}
              {error ? <p className="upload-error">{error}</p> : null}
            </div>
          </section>

          <section className="lifecycle" id="lifecycle">
            <div className="section-head">
              <div>
                <h2>The Redaction Lifecycle</h2>
                <p>
                  Same flow for PDFs and pasted text: bring in content, review what
                  the model found, then export a redacted PDF or copyable text.
                </p>
              </div>
              <div className="section-count">01-03</div>
            </div>

            <div className="lifecycle-grid">
              <article className="step-card">
                <div className="step-number">01</div>
                <h3>Import</h3>
                <div className="step-visual visual-upload">
                  <div className="paper-stack" />
                  <div className="paper-upload-arrow" />
                </div>
                <p>
                  Upload a PDF for structured extraction and page previews, or paste
                  plain text for immediate detection and on-page redacted output.
                </p>
              </article>

              <article className="step-card step-offset">
                <div className="step-number">02</div>
                <h3>Review</h3>
                <div className="step-visual visual-review">
                  <div className="review-lines" />
                  <div className="entity-chip chip-person">PERSON</div>
                  <div className="entity-chip chip-email">EMAIL</div>
                  <div className="entity-chip chip-id">ID</div>
                </div>
                <p>
                  The NLP model detects names, addresses, IDs, financial details,
                  and related sensitive entities for user verification.
                </p>
              </article>

              <article className="step-card step-deep">
                <div className="step-number">03</div>
                <h3>Export</h3>
                <div className="step-visual visual-download">
                  <div className="device-frame" />
                  <div className="device-page" />
                  <div className="device-redactions" />
                </div>
                <p>
                  Download a redacted PDF when you started from a file, or copy
                  redacted text when you pasted—both paths support the same review
                  and entity controls.
                </p>
              </article>
            </div>
          </section>

          <section className="trust-grid" id="trust">
            <article className="trust-panel trust-panel-primary">
              <p className="eyebrow">Project Overview</p>
              <h2>Built around NLP, PDF mapping, text redaction, and user review.</h2>
              <p>
                The system combines a custom NER model, coordinate mapping for PDFs,
                a plain-text redaction path with copy-friendly output, and a shared
                review UI so you can validate or override detections before export.
              </p>
            </article>

            <article className="trust-panel trust-panel-soft">
              <div className="trust-icon">NLP</div>
              <h3>Entity Detection</h3>
              <p>
                spaCy-based detection finds sensitive spans in both extracted PDF text
                and pasted content before anything is redacted.
              </p>
            </article>

            <article className="trust-panel trust-panel-accent">
              <div className="trust-icon">PDF</div>
              <h3>PDF Mapping</h3>
              <p>
                For PDFs, spans map to page boxes; pasted text uses the same detections with a
                character-level redaction path.
              </p>
            </article>

            <article className="trust-panel trust-panel-wide">
              <div>
                <h3>Human-in-the-Loop Review</h3>
                <p>Users can inspect detections, disable false positives, and add manual redactions before export.</p>
              </div>
              <span className="trust-arrow">&rarr;</span>
            </article>
          </section>
        </main>

        <footer className="footer">
          <div className="brand">Redactinator</div>
          <div className="footer-links">
            <a href="#upload">Start</a>
            <a href="#lifecycle">How It Works</a>
            <a href="#trust">About</a>
          </div>
          <div className="footer-copy">2026 Redactinator. All rights reserved.</div>
        </footer>
      </div>
    </>
  );
}
