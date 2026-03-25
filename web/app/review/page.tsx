"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

import { LoadingScreen } from "../../components/loading-screen";
import { SessionGuard } from "../../components/session-guard";
import { mapEntities, redactPdf } from "../../lib/api";
import { useSession } from "../../lib/session";
import type { RedactionEntity } from "../../lib/types";

const MIN_LOADING_MS = 1100;

function Toggle({ active, alert = false }: { active: boolean; alert?: boolean }) {
  return (
    <span
      className={[
        "inspector-toggle",
        active ? "is-active" : "",
        alert ? "is-alert" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-hidden="true"
    >
      <span className="inspector-toggle-knob" />
    </span>
  );
}

function inferGroup(label: string) {
  const normalized = label.toUpperCase();
  if (
    [
      "NAME",
      "PERSON",
      "ADDRESS",
      "EMAIL",
      "PHONE",
      "ORG",
      "ORGANIZATION",
      "LOCATION",
    ].includes(normalized)
  ) {
    return "Personal Data";
  }
  if (["MONEY", "CREDIT_CARD", "ID", "PASSPORT"].includes(normalized)) {
    return "Financial";
  }
  return "Technical";
}

function inferTone(entity: RedactionEntity) {
  if (!entity.enabled) {
    return "muted";
  }
  if (["MONEY", "CREDIT_CARD", "ID", "PASSPORT"].includes(entity.label.toUpperCase())) {
    return "alert";
  }
  return "default";
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function ReviewContent() {
  const router = useRouter();
  const { session, setEntities, setMappedEntities, setResult } = useSession();
  const [manualText, setManualText] = useState("");
  const [manualLabel, setManualLabel] = useState("CUSTOM");
  const [manualStart, setManualStart] = useState("");
  const [manualEnd, setManualEnd] = useState("");
  const [manualQuery, setManualQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState<string | null>(null);
  const [isRedacting, setIsRedacting] = useState(false);
  const textPreviewRef = useRef<HTMLPreElement | null>(null);

  if (!session) {
    return null;
  }

  const groupedEntities = useMemo(() => {
    const grouped = new Map<string, RedactionEntity[]>();
    for (const entity of session.entities) {
      const key = inferGroup(entity.label);
      grouped.set(key, [...(grouped.get(key) ?? []), entity]);
    }
    return Array.from(grouped.entries()).map(([name, items]) => ({
      name,
      action: "Select All",
      items,
    }));
  }, [session.entities]);

  const enabledCount = session.entities.filter((entity) => entity.enabled).length;
  const score = session.entities.length === 0 ? 0 : Math.round((enabledCount / session.entities.length) * 100);
  const pagePreview = session.pages[currentPage];
  const overlayRects = session.mappedEntities.filter(
    (entity) => entity.page === currentPage && entity.enabled
  );
  const manualMatches = useMemo(() => {
    const query = manualQuery.trim();
    if (!query || !session.text) {
      return [];
    }

    const regex = new RegExp(escapeRegExp(query), "gi");
    const matches: Array<{ start: number; end: number; text: string; context: string }> = [];
    let match: RegExpExecArray | null;

    while ((match = regex.exec(session.text)) !== null && matches.length < 8) {
      const start = match.index;
      const text = match[0];
      const end = start + text.length;
      const contextStart = Math.max(0, start - 36);
      const contextEnd = Math.min(session.text.length, end + 36);
      const prefix = contextStart > 0 ? "..." : "";
      const suffix = contextEnd < session.text.length ? "..." : "";
      const context = `${prefix}${session.text.slice(contextStart, contextEnd)}${suffix}`;
      matches.push({ start, end, text, context });

      if (match.index === regex.lastIndex) {
        regex.lastIndex += 1;
      }
    }

    return matches;
  }, [manualQuery, session.text]);

  const toggleEntity = (target: RedactionEntity) => {
    setEntities(
      session.entities.map((entity) =>
        entity === target ? { ...entity, enabled: !entity.enabled } : entity
      )
    );
  };

  const selectAllGroup = (groupName: string) => {
    setEntities(
      session.entities.map((entity) =>
        inferGroup(entity.label) === groupName ? { ...entity, enabled: true } : entity
      )
    );
  };

  const addManualRedaction = () => {
    const start = Number(manualStart);
    const end = Number(manualEnd);
    if (!manualText.trim() || !manualLabel.trim()) {
      setError("Manual redactions need text and label.");
      return;
    }
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start) {
      setError("Manual redactions need valid numeric start and end offsets.");
      return;
    }

    const nextEntities = [
      ...session.entities,
      {
        text: manualText.trim(),
        label: manualLabel.trim().toUpperCase(),
        start,
        end,
        enabled: true,
        source: "manual" as const,
      },
    ];

    setEntities(nextEntities);
    void mapEntities(session.documentId, nextEntities)
      .then((response) => {
        setMappedEntities(response.mappedEntities);
        setManualText("");
        setManualLabel("CUSTOM");
        setManualStart("");
        setManualEnd("");
        setManualQuery("");
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to map manual redaction.");
      });
  };

  const captureSelection = () => {
    const container = textPreviewRef.current;
    const selection = window.getSelection();
    if (!container || !selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return;
    }

    const range = selection.getRangeAt(0);
    if (!container.contains(range.commonAncestorContainer)) {
      return;
    }

    const selectedText = selection.toString();
    if (!selectedText.trim()) {
      return;
    }

    const preRange = range.cloneRange();
    preRange.selectNodeContents(container);
    preRange.setEnd(range.startContainer, range.startOffset);
    const start = preRange.toString().length;
    const end = start + selectedText.length;

    setManualText(selectedText);
    setManualStart(String(start));
    setManualEnd(String(end));
    setError(null);
  };

  const applyManualMatch = (start: number, end: number, text: string) => {
    setManualText(text);
    setManualStart(String(start));
    setManualEnd(String(end));
    setError(null);
  };

  const handleConfirm = async () => {
    setError(null);
    setIsRedacting(true);
    try {
      const [result] = await Promise.all([
        redactPdf(session.documentId, session.entities),
        new Promise((resolve) => window.setTimeout(resolve, MIN_LOADING_MS)),
      ]);
      setResult(result);
      router.push("/result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to redact PDF.");
      setIsRedacting(false);
    }
  };

  return (
    <>
      {isRedacting ? (
        <LoadingScreen
          title="Applying redactions"
          subtitle="Mapping approved entities back to the PDF and generating the final redacted document."
          steps={[
            "Locking approved selections",
            "Mapping text spans to page regions",
            "Rendering the final redacted PDF",
          ]}
        />
      ) : null}
      <div className="review-shell">
        <header className="review-topbar">
          <div className="review-brand-wrap">
            <a className="brand" href="/">
              Redactinator
            </a>
            <nav className="review-topnav">
              <a href="/#lifecycle">How It Works</a>
              <a href="/#trust">Project</a>
            </nav>
          </div>
          <a className="button button-primary" href="/">
            New Upload
          </a>
        </header>

        <div className="review-layout">
          <aside className="workflow-rail">
            <div className="workflow-project">
              <h2>Redaction Review</h2>
              <p>Smart Document Redaction</p>
            </div>

            <nav className="workflow-nav">
              <a className="workflow-link" href="/">
                <span className="workflow-icon">UP</span>
                <span>Upload</span>
              </a>
              <a className="workflow-link is-active" href="/review">
                <span className="workflow-icon">RV</span>
                <span>Review</span>
              </a>
              <a className="workflow-link" href="/result">
                <span className="workflow-icon">DL</span>
                <span>Download</span>
              </a>
            </nav>
          </aside>

          <main className="review-workspace">
            <section className="document-stage">
              <div className="document-paper">
                <article className="document-body">
                  <div className="document-header">
                    <div className="document-logo-block" />
                    <div className="document-ref">
                      <p>SMART DOCUMENT REDACTION</p>
                      <span>Ref: {session.documentId.slice(0, 12)}</span>
                    </div>
                  </div>

                  <h1>Review Detected Content</h1>
                  <p className="document-meta">
                    {session.filename} - {session.pageCount} page{session.pageCount === 1 ? "" : "s"}
                  </p>

                  <div className="pdf-preview-frame">
                    {pagePreview ? (
                      <div
                        className="pdf-preview-page"
                        style={{
                          aspectRatio: `${pagePreview.width} / ${pagePreview.height}`,
                          width: `${zoom}%`,
                        }}
                      >
                        <img
                          src={pagePreview.imageUrl}
                          alt={`Preview of page ${currentPage + 1}`}
                          className="pdf-preview-image"
                        />
                        {overlayRects.map((entity) => {
                          const [x0, y0, x1, y1] = entity.rect;
                          return (
                            <div
                              key={`${entity.label}-${entity.start}-${entity.end}-${x0}-${y0}`}
                              className="pdf-overlay-rect"
                              title={`${entity.label}: ${entity.text}`}
                              style={{
                                left: `${(x0 / pagePreview.width) * 100}%`,
                                top: `${(y0 / pagePreview.height) * 100}%`,
                                width: `${((x1 - x0) / pagePreview.width) * 100}%`,
                                height: `${((y1 - y0) / pagePreview.height) * 100}%`,
                              }}
                            />
                          );
                        })}
                      </div>
                    ) : (
                      <div className="pdf-preview-empty">No page preview available.</div>
                    )}
                  </div>

                  <div className="document-copy">
                    <div className="document-copy-head">
                      <p>Select text below to auto-fill a manual redaction from the extracted document text.</p>
                    </div>
                    <pre
                      ref={textPreviewRef}
                      className="document-text-preview"
                      onMouseUp={captureSelection}
                      onKeyUp={captureSelection}
                    >
                      {session.text || "No extracted text preview available."}
                    </pre>
                  </div>
                </article>
              </div>
            </section>

            <aside className="inspector-panel">
              <div className="inspector-header">
                <h2>Entity Inspector</h2>
                <span>{session.entities.length} DETECTED</span>
              </div>

              <div className="inspector-groups">
                {groupedEntities.map((group) => (
                  <section className="inspector-group" key={group.name}>
                    <div className="inspector-group-head">
                      <p>{group.name}</p>
                      <button type="button" onClick={() => selectAllGroup(group.name)}>
                        {group.action}
                      </button>
                    </div>

                    <div className="inspector-list">
                      {group.items.map((item) => (
                        <article
                          className={[
                            "inspector-card",
                            inferTone(item) === "alert" ? "is-alert" : "",
                            inferTone(item) === "muted" ? "is-muted" : "",
                          ]
                            .filter(Boolean)
                            .join(" ")}
                          key={`${group.name}-${item.label}-${item.text}-${item.start}`}
                        >
                          <div className="inspector-card-top">
                            <span className="inspector-badge">{item.label}</span>
                            <div className="inspector-actions">
                              {inferTone(item) === "alert" ? (
                                <span className="inspector-warning">!</span>
                              ) : (
                                <button type="button">{item.source === "manual" ? "Manual" : "Model"}</button>
                              )}
                              <Toggle active={item.enabled} alert={inferTone(item) === "alert"} />
                              <button type="button" onClick={() => toggleEntity(item)}>
                                {item.enabled ? "Disable" : "Enable"}
                              </button>
                            </div>
                          </div>
                          <p>{item.text}</p>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}

                <div className="manual-form">
                  <h3>Add Manual Redaction</h3>
                  <p className="manual-form-help">
                    Search for text and pick the right match, or highlight text in the extracted preview to auto-fill the fields.
                  </p>
                  <input
                    value={manualQuery}
                    onChange={(event) => setManualQuery(event.target.value)}
                    placeholder="Search document text"
                  />
                  {manualQuery.trim() ? (
                    <div className="manual-search-results">
                      {manualMatches.length > 0 ? (
                        manualMatches.map((match) => (
                          <button
                            key={`${match.start}-${match.end}`}
                            className="manual-search-result"
                            type="button"
                            onClick={() => applyManualMatch(match.start, match.end, match.text)}
                          >
                            <strong>{match.text}</strong>
                            <span>{match.context}</span>
                          </button>
                        ))
                      ) : (
                        <p className="manual-search-empty">No matches found in the extracted text.</p>
                      )}
                    </div>
                  ) : null}
                  <input
                    value={manualText}
                    onChange={(event) => setManualText(event.target.value)}
                    placeholder="Text"
                  />
                  <input
                    value={manualLabel}
                    onChange={(event) => setManualLabel(event.target.value)}
                    placeholder="Label"
                  />
                  <div className="manual-form-row">
                    <input
                      value={manualStart}
                      onChange={(event) => setManualStart(event.target.value)}
                      placeholder="Start"
                      inputMode="numeric"
                    />
                    <input
                      value={manualEnd}
                      onChange={(event) => setManualEnd(event.target.value)}
                      placeholder="End"
                      inputMode="numeric"
                    />
                  </div>
                  <button className="manual-redaction" type="button" onClick={addManualRedaction}>
                    <span>+</span>
                    <span>Add Manual Redaction</span>
                  </button>
                </div>
              </div>

              <div className="inspector-footer">
                <div className="score-row">
                  <p>Estimated Safety Score</p>
                  <span>{score}%</span>
                </div>
                <div className="score-bar">
                  <span style={{ width: `${score}%` }} />
                </div>
                {error ? <p className="form-error">{error}</p> : null}
                <button
                  className="button button-primary inspector-confirm"
                  type="button"
                  onClick={handleConfirm}
                  disabled={isRedacting}
                >
                  {isRedacting ? "Generating Output..." : "Confirm & Redact"}
                </button>
              </div>
            </aside>
          </main>
        </div>

        <div className="floating-toolbar">
          <div className="toolbar-group">
            <button type="button" onClick={() => setZoom((value) => Math.min(180, value + 10))}>
              +
            </button>
            <span>{zoom}%</span>
            <button type="button" onClick={() => setZoom((value) => Math.max(70, value - 10))}>
              -
            </button>
          </div>
          <div className="toolbar-group">
            <button
              type="button"
              onClick={() => setCurrentPage((page) => Math.max(0, page - 1))}
            >
              {"<"}
            </button>
            <span>Page {currentPage + 1} of {session.pageCount}</span>
            <button
              type="button"
              onClick={() =>
                setCurrentPage((page) => Math.min(session.pageCount - 1, page + 1))
              }
            >
              {">"}
            </button>
          </div>
          <div className="toolbar-group">
            <button type="button" onClick={() => setCurrentPage(0)}>
              First
            </button>
            <button type="button" onClick={() => setZoom(100)}>
              Reset
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default function ReviewPage() {
  return (
    <SessionGuard>
      <ReviewContent />
    </SessionGuard>
  );
}
