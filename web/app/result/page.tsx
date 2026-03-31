"use client";

import { useMemo, useState } from "react";

import { SessionGuard } from "../../components/session-guard";
import { useSession } from "../../lib/session";
import type { PdfRedactResult, RedactionResult } from "../../lib/types";

function isPdfRedactResult(result: RedactionResult): result is PdfRedactResult {
  if ("kind" in result) {
    return result.kind === "pdf";
  }
  return "downloadUrl" in result;
}

function ResultContent() {
  const { clearSession, session } = useSession();
  const [currentPage, setCurrentPage] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [copied, setCopied] = useState(false);

  if (!session || !session.result) {
    return null;
  }

  const result = session.result;
  const pdfResult = isPdfRedactResult(result) ? result : null;

  const summaryItems = Object.entries(result.summary).map(([label, count]) => ({
    label,
    count: String(count).padStart(2, "0"),
  }));

  const previewImageUrl = pdfResult
    ? `${pdfResult.previewBaseUrl}/${currentPage}/image`
    : "";
  const previewPage = session.pages[currentPage];
  const totalPages = session.pageCount;
  const topSummary = useMemo(() => summaryItems.slice(0, 4), [summaryItems]);

  const handleCopyRedacted = async () => {
    if (!("redactedText" in result)) {
      return;
    }
    try {
      await navigator.clipboard.writeText(result.redactedText);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="result-shell">
      <aside className="result-rail">
        <div className="result-rail-head">
          <a className="brand" href="/">
            Redactinator
          </a>
          <div>
            <p>Redaction Output</p>
            <span>Smart Document Redaction</span>
          </div>
        </div>

        <nav className="result-rail-nav">
          <a className="workflow-link" href="/">
            <span className="workflow-icon">UP</span>
            <span>Upload</span>
          </a>
          <a className="workflow-link" href="/review">
            <span className="workflow-icon">RV</span>
            <span>Review</span>
          </a>
          <a className="workflow-link is-active" href="/result">
            <span className="workflow-icon">RS</span>
            <span>Result</span>
          </a>
        </nav>

        <div className="result-rail-foot">
          <a className="workflow-meta" href="#">
            Settings
          </a>
          <a className="workflow-meta" href="#">
            Support
          </a>
        </div>
      </aside>

      <main className="result-main">
        <div className="result-canvas result-canvas-compact">
          <header className="result-header">
            <div>
              <div className="result-status">
                <span className="result-status-icon">OK</span>
                <span>Redaction Successful</span>
              </div>
              <h1>Redaction Complete</h1>
              <p>
                {pdfResult ? (
                  <>
                    Your PDF has been processed, reviewed, and redacted. Use the
                    preview to inspect the final output before downloading.
                  </>
                ) : (
                  <>
                    Your text has been redacted according to the entities you kept enabled. Copy the
                    output below or start over with new content.
                  </>
                )}
              </p>
            </div>

            <div className="result-header-actions">
              <a
                className="result-link-action"
                href="/"
                onClick={() => {
                  clearSession();
                }}
              >
                Start Over
              </a>
              {pdfResult ? (
                <a className="button button-primary result-download" href={pdfResult.downloadUrl}>
                  Download Redacted PDF
                </a>
              ) : (
                <button
                  type="button"
                  className="button button-primary result-download"
                  onClick={handleCopyRedacted}
                >
                  {copied ? "Copied" : "Copy redacted text"}
                </button>
              )}
            </div>
          </header>

          <div className="result-grid result-grid-compact">
            <section className="result-preview-card">
              <div className="result-preview-head">
                <h2>
                  {pdfResult ? `Preview: ${pdfResult.filename}` : "Redacted text"}
                </h2>
                {pdfResult ? (
                  <div className="result-preview-tools">
                    <button type="button" onClick={() => setZoom((value) => Math.min(180, value + 10))}>
                      +
                    </button>
                    <button type="button" onClick={() => setZoom((value) => Math.max(70, value - 10))}>
                      -
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="result-document result-document-real">
                {pdfResult ? (
                  <>
                    {previewPage ? (
                      <div
                        className="pdf-preview-page result-preview-page"
                        style={{
                          aspectRatio: `${previewPage.width} / ${previewPage.height}`,
                          width: `${zoom}%`,
                        }}
                      >
                        <img
                          src={previewImageUrl}
                          alt={`Redacted preview page ${currentPage + 1}`}
                          className="pdf-preview-image"
                        />
                      </div>
                    ) : (
                      <div className="pdf-preview-empty">No preview available.</div>
                    )}

                    <div className="result-document-toolbar">
                      <button
                        type="button"
                        onClick={() => setCurrentPage((page) => Math.max(0, page - 1))}
                      >
                        {"<"}
                      </button>
                      <span>
                        Page {currentPage + 1} of {totalPages}
                      </span>
                      <button
                        type="button"
                        onClick={() => setCurrentPage((page) => Math.min(totalPages - 1, page + 1))}
                      >
                        {">"}
                      </button>
                      <div className="result-toolbar-divider" />
                      <button type="button" onClick={() => setZoom(100)}>
                        Reset
                      </button>
                    </div>
                  </>
                ) : (
                  <pre className="result-redacted-text" tabIndex={0}>
                    {"redactedText" in result ? result.redactedText : ""}
                  </pre>
                )}
              </div>
            </section>

            <aside className="result-side">
              <section className="result-panel">
                <h3>Redaction Summary</h3>
                <div className="summary-total">
                  <div className="summary-total-bar" />
                  <div>
                    <p>{result.entityCount} entities removed</p>
                    <span>Total applied redactions</span>
                  </div>
                  <strong>OK</strong>
                </div>

                <div className="summary-breakdown">
                  <p>Entity Breakdown</p>
                  <ul>
                    {topSummary.map((item) => (
                      <li key={item.label}>
                        <span>{item.label}</span>
                        <strong>{item.count}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              </section>
            </aside>
          </div>

          <footer className="result-footer result-footer-compact">
            <a
              className="result-upload-another"
              href="/"
              onClick={() => {
                clearSession();
              }}
            >
              Upload Another File
            </a>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default function ResultPage() {
  return (
    <SessionGuard requireResult>
      <ResultContent />
    </SessionGuard>
  );
}
