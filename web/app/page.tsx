"use client";

import { useRouter } from "next/navigation";
import { useState, type ChangeEvent } from "react";

import { LoadingScreen } from "../components/loading-screen";
import { analyzePdf } from "../lib/api";
import { useSession } from "../lib/session";

const MIN_LOADING_MS = 1100;

export default function Home() {
  const router = useRouter();
  const { clearSession, setAnalysis } = useSession();
  const [error, setError] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

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

  return (
    <>
      {isAnalyzing ? (
        <LoadingScreen
          title="Analyzing document"
          subtitle="Extracting PDF text, running entity detection, and preparing the review workspace."
          steps={[
            "Reading PDF structure",
            "Detecting sensitive entities",
            "Preparing review preview",
          ]}
        />
      ) : null}
      <div className="site-shell">
        <header className="topbar">
          <div className="brand">Redactinator</div>
          <nav className="topnav">
            <a href="#lifecycle">How It Works</a>
            <a href="#trust">Project</a>
            <a className="button button-primary" href="#upload">
              Upload PDF
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
                PDF data faster.
              </h1>
              <p className="hero-text">
                Redactinator is our Smart Document Redaction System that combines
                Named Entity Recognition, PDF processing, and human-in-the-loop
                review to detect and permanently remove sensitive information from
                uploaded documents.
              </p>
              <div className="hero-points">
                <span>NER-based detection</span>
                <span>Human review before export</span>
              </div>
            </div>

            <div className="upload-panel" id="upload">
              <div className="upload-glow" />
              <div className="upload-card">
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
                  <p>Upload a PDF to extract text, review entities, and generate a redacted copy</p>
                  <span className="button button-primary">Select Document</span>
                  <small>PDF files up to 50MB</small>
                </label>
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
                  A focused three-step flow: bring in the document, review what
                  the system found, and export a clean copy with confidence.
                </p>
              </div>
              <div className="section-count">01-03</div>
            </div>

            <div className="lifecycle-grid">
              <article className="step-card">
                <div className="step-number">01</div>
                <h3>Upload</h3>
                <div className="step-visual visual-upload">
                  <div className="paper-stack" />
                  <div className="paper-upload-arrow" />
                </div>
                <p>
                  Upload the original PDF and let the system extract its text and
                  page structure for analysis.
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
                <h3>Download</h3>
                <div className="step-visual visual-download">
                  <div className="device-frame" />
                  <div className="device-page" />
                  <div className="device-redactions" />
                </div>
                <p>
                  Approved entities are mapped back to PDF coordinates and
                  permanently redacted in the final downloadable file.
                </p>
              </article>
            </div>
          </section>

          <section className="trust-grid" id="trust">
            <article className="trust-panel trust-panel-primary">
              <p className="eyebrow">Project Overview</p>
              <h2>Built around NLP, PDF mapping, and user review.</h2>
              <p>
                The system is designed as a modular university project with three
                connected parts: the NER model, the PDF redaction engine, and the
                frontend review workflow.
              </p>
            </article>

            <article className="trust-panel trust-panel-soft">
              <div className="trust-icon">NLP</div>
              <h3>Entity Detection</h3>
              <p>spaCy-based detection identifies sensitive text spans before redaction.</p>
            </article>

            <article className="trust-panel trust-panel-accent">
              <div className="trust-icon">PDF</div>
              <h3>PDF Mapping</h3>
              <p>Detected offsets are mapped back to page coordinates for accurate redaction.</p>
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
