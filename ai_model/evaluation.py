"""
NER evaluation: spaCy Scorer metrics (precision / recall / F1), per-label scores,
error analysis, training-curve plots, and report-ready figures/tables.

When using ``train_model.py``, all of these are written to a single folder
(``--artifacts-dir``, default ``model/ner_model/artifacts``).
"""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from spacy.language import Language
from spacy.scorer import Scorer
from spacy.training import Example

logger = logging.getLogger(__name__)

# Same as notebook: optional label aliasing for analysis display
LABEL_NORMALIZATION: dict[str, str] = {
    "GPE": "LOCATION",
    "LOC": "LOCATION",
}


def normalize_label(label: str) -> str:
    return LABEL_NORMALIZATION.get(label, label)


def normalize_pred(doc: Any) -> set[tuple[str, str]]:
    return {(ent.text.lower(), normalize_label(ent.label_)) for ent in doc.ents}


def normalize_true(doc: Any) -> set[tuple[str, str]]:
    return {(ent.text.lower(), normalize_label(ent.label_)) for ent in doc.ents}


def evaluate(nlp: Language, examples: list[Example]) -> dict[str, Any]:
    """Overall + per-type entity scores (matches notebook Scorer usage)."""
    scorer = Scorer()
    preds: list[Example] = []
    for ex in examples:
        pred = nlp(ex.reference.text)
        preds.append(Example(pred, ex.reference))
    return scorer.score(preds)


def format_overall_metrics(scores: dict[str, Any]) -> str:
    p = scores.get("ents_p")
    r = scores.get("ents_r")
    f = scores.get("ents_f")
    return f"Precision: {p:.4f} | Recall: {r:.4f} | F1: {f:.4f}"


def log_metrics(scores: dict[str, Any], *, prefix: str = "") -> None:
    """Log micro entity metrics and per-label precision / recall / F1."""
    pfx = f"{prefix} " if prefix else ""
    logger.info("%s%s", pfx, format_overall_metrics(scores))

    per_type = scores.get("ents_per_type") or {}
    if not per_type:
        return
    logger.info("%sPer-label entity scores:", pfx)
    for label in sorted(per_type.keys()):
        m = per_type[label]
        if isinstance(m, dict):
            logger.info(
                "  %s — P: %.4f  R: %.4f  F1: %.4f",
                label,
                m.get("p", 0.0),
                m.get("r", 0.0),
                m.get("f", 0.0),
            )


def print_metrics(scores: dict[str, Any], *, prefix: str = "") -> None:
    """Console-friendly metrics (notebook-style)."""
    pfx = f"{prefix} " if prefix else ""
    print(f"{pfx}Precision:", round(scores.get("ents_p", 0.0), 4))
    print(f"{pfx}Recall   :", round(scores.get("ents_r", 0.0), 4))
    print(f"{pfx}F1       :", round(scores.get("ents_f", 0.0), 4))
    per_type = scores.get("ents_per_type") or {}
    if per_type:
        print(f"{pfx}--- Per label ---")
        for label in sorted(per_type.keys()):
            m = per_type[label]
            if isinstance(m, dict):
                print(
                    f"  {label}: P={round(m.get('p', 0.0), 4)} "
                    f"R={round(m.get('r', 0.0), 4)} F1={round(m.get('f', 0.0), 4)}"
                )


# ---------------------------------------------------------------------------
# Report: structured numbers + CSV / JSON
# ---------------------------------------------------------------------------


def scores_to_per_label_rows(scores: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows for tables: label, precision, recall, f1."""
    per_type = scores.get("ents_per_type") or {}
    rows: list[dict[str, Any]] = []
    for label in sorted(per_type.keys()):
        m = per_type[label]
        if not isinstance(m, dict):
            continue
        rows.append(
            {
                "label": label,
                "precision": round(float(m.get("p", 0.0)), 6),
                "recall": round(float(m.get("r", 0.0)), 6),
                "f1": round(float(m.get("f", 0.0)), 6),
            }
        )
    return rows


def overall_metrics_dict(scores: dict[str, Any]) -> dict[str, float]:
    return {
        "precision": float(scores.get("ents_p") or 0.0),
        "recall": float(scores.get("ents_r") or 0.0),
        "f1": float(scores.get("ents_f") or 0.0),
    }


def export_per_label_metrics_csv(scores: dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = scores_to_per_label_rows(scores)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["label", "precision", "recall", "f1"])
        w.writeheader()
        w.writerows(rows)
    logger.info("Wrote %s", path)


def export_metrics_json(scores: dict[str, Any], path: Path) -> None:
    """Overall + per-label metrics for the report (machine-readable)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "overall": overall_metrics_dict(scores),
        "per_label": scores_to_per_label_rows(scores),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s", path)


def plot_metrics_report_figures(
    scores: dict[str, Any],
    *,
    save_dir: Path | None = None,
    show: bool = False,
) -> None:
    """
    Figures for papers/reports: grouped P/R/F1 by label, overall bars, per-label F1 heat strip.
    Saves under ``save_dir`` when set.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    per_rows = scores_to_per_label_rows(scores)
    labels = [r["label"] for r in per_rows]
    if not labels:
        logger.warning("No per-label scores to plot.")
        return

    ps = [r["precision"] for r in per_rows]
    rs = [r["recall"] for r in per_rows]
    fs = [r["f1"] for r in per_rows]
    x = np.arange(len(labels))
    w = 0.25

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.5), 5))
    ax.bar(x - w, ps, width=w, label="Precision", color="#4472c4")
    ax.bar(x, rs, width=w, label="Recall", color="#ed7d31")
    ax.bar(x + w, fs, width=w, label="F1", color="#70ad47")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Entity recognition: precision, recall, F1 by label")
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    if save_dir is not None:
        sd = Path(save_dir)
        sd.mkdir(parents=True, exist_ok=True)
        p = sd / "report_per_label_prf.png"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        logger.info("Saved %s", p)
    if show:
        plt.show()
    else:
        plt.close(fig)

    # Overall micro metrics
    ov = overall_metrics_dict(scores)
    fig2, ax2 = plt.subplots(figsize=(5, 4))
    names = ["Precision", "Recall", "F1"]
    vals = [ov["precision"], ov["recall"], ov["f1"]]
    colors = ["#4472c4", "#ed7d31", "#70ad47"]
    ax2.bar(names, vals, color=colors)
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("Score")
    ax2.set_title("Overall entity metrics (micro)")
    for i, v in enumerate(vals):
        ax2.text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=11)
    fig2.tight_layout()
    if save_dir is not None:
        p2 = Path(save_dir) / "report_overall_metrics.png"
        fig2.savefig(p2, dpi=200, bbox_inches="tight")
        logger.info("Saved %s", p2)
    if show:
        plt.show()
    else:
        plt.close(fig2)

    # F1-only horizontal bar (compact slide)
    fig3, ax3 = plt.subplots(figsize=(max(6, len(labels) * 0.35), 4))
    y = np.arange(len(labels))
    ax3.barh(y, fs, color="#2e75b6")
    ax3.set_yticks(y)
    ax3.set_yticklabels(labels)
    ax3.set_xlim(0, 1.05)
    ax3.set_xlabel("F1")
    ax3.set_title("F1 score by entity type")
    ax3.grid(axis="x", alpha=0.3)
    fig3.tight_layout()
    if save_dir is not None:
        p3 = Path(save_dir) / "report_f1_by_label.png"
        fig3.savefig(p3, dpi=200, bbox_inches="tight")
        logger.info("Saved %s", p3)
    if show:
        plt.show()
    else:
        plt.close(fig3)


# ---------------------------------------------------------------------------
# Error analysis: aggregates + report figures
# ---------------------------------------------------------------------------


def collect_errors(
    nlp: Language,
    docs: list[Any],
) -> list[tuple[str, set[tuple[str, str]], set[tuple[str, str]]]]:
    """All docs where predicted entity sets differ from gold (normalized)."""
    errors: list[tuple[str, set[tuple[str, str]], set[tuple[str, str]]]] = []
    for doc in docs:
        pred_doc = nlp(doc.text)
        pred_set = normalize_pred(pred_doc)
        true_set = normalize_true(doc)
        if pred_set != true_set:
            errors.append((doc.text, pred_set, true_set))
    return errors


def error_statistics(
    errors: list[tuple[str, set[tuple[str, str]], set[tuple[str, str]]]],
) -> dict[str, Any]:
    """
    Aggregate missed / extra counts by label and same-text label-confusion pairs.
    Uses (surface_lower, label) tuples from the notebook error sets.
    """
    missed_by_label: Counter[str] = Counter()
    extra_by_label: Counter[str] = Counter()
    confusion_gold_pred: Counter[tuple[str, str]] = Counter()

    for _text, pred, true in errors:
        missed = true - pred
        extra = pred - true
        for _surface, lab in missed:
            missed_by_label[lab] += 1
        for _surface, lab in extra:
            extra_by_label[lab] += 1

        # Same surface string: gold label -> predicted label (wrong-label mistakes)
        by_text_missed: dict[str, list[str]] = defaultdict(list)
        by_text_extra: dict[str, list[str]] = defaultdict(list)
        for surf, lab in missed:
            by_text_missed[surf].append(lab)
        for surf, lab in extra:
            by_text_extra[surf].append(lab)
        for surf in set(by_text_missed) & set(by_text_extra):
            for gl in by_text_missed[surf]:
                for pl in by_text_extra[surf]:
                    confusion_gold_pred[(gl, pl)] += 1

    n_missed = sum(missed_by_label.values())
    n_extra = sum(extra_by_label.values())

    return {
        "n_docs_with_errors": len(errors),
        "n_span_missed": n_missed,
        "n_span_extra": n_extra,
        "missed_by_label": dict(sorted(missed_by_label.items())),
        "extra_by_label": dict(sorted(extra_by_label.items())),
        "label_confusion_counts": {
            f"{g}→{p}": c
            for (g, p), c in sorted(
                confusion_gold_pred.items(), key=lambda x: (-x[1], x[0])
            )
        },
    }


def export_error_statistics_json(stats: dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    logger.info("Wrote %s", path)


def plot_error_analysis_figures(
    stats: dict[str, Any],
    *,
    save_dir: Path | None = None,
    show: bool = False,
) -> None:
    """
    Bar charts: missed vs extra by label; optional confusion heatmap for gold→pred pairs.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    missed = stats.get("missed_by_label") or {}
    extra = stats.get("extra_by_label") or {}
    all_labels = sorted(set(missed.keys()) | set(extra.keys()))
    if not all_labels:
        logger.warning("No error aggregates to plot.")
        return

    m_vals = [missed.get(l, 0) for l in all_labels]
    e_vals = [extra.get(l, 0) for l in all_labels]
    x = np.arange(len(all_labels))
    w = 0.38

    fig, ax = plt.subplots(figsize=(max(8, len(all_labels) * 0.45), 5))
    ax.bar(x - w / 2, m_vals, width=w, label="Missed (FN)", color="#c55a11")
    ax.bar(x + w / 2, e_vals, width=w, label="Extra (FP)", color="#5b9bd5")
    ax.set_xticks(x)
    ax.set_xticklabels(all_labels, rotation=45, ha="right")
    ax.set_ylabel("Entity count")
    ax.set_title("Error analysis: missed vs extra predictions by label")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    if save_dir is not None:
        sd = Path(save_dir)
        sd.mkdir(parents=True, exist_ok=True)
        p = sd / "report_errors_missed_vs_extra.png"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        logger.info("Saved %s", p)
    if show:
        plt.show()
    else:
        plt.close(fig)

    # Stacked summary: total FN vs FP
    fig2, ax2 = plt.subplots(figsize=(4, 4))
    totals = [stats.get("n_span_missed", 0), stats.get("n_span_extra", 0)]
    ax2.bar(["Missed (FN)", "Extra (FP)"], totals, color=["#c55a11", "#5b9bd5"])
    ax2.set_ylabel("Count")
    ax2.set_title("Total span-level errors")
    for i, v in enumerate(totals):
        ax2.text(i, v + max(totals, default=1) * 0.02, str(v), ha="center")
    fig2.tight_layout()
    if save_dir is not None:
        p2 = Path(save_dir) / "report_errors_totals.png"
        fig2.savefig(p2, dpi=200, bbox_inches="tight")
        logger.info("Saved %s", p2)
    if show:
        plt.show()
    else:
        plt.close(fig2)

    # Heatmap for gold→pred confusion (only pairs with count > 0)
    conf_raw = stats.get("label_confusion_counts") or {}
    if not conf_raw:
        return

    pairs = []
    for k, c in conf_raw.items():
        if "→" in k:
            g, _, p = k.partition("→")
        else:
            g, _, p = k.partition("|")
        pairs.append((g, p, c))
    gold_labels = sorted({a for a, _, _ in pairs})
    pred_labels = sorted({b for _, b, _ in pairs})
    if not gold_labels or not pred_labels:
        return

    mat = np.zeros((len(gold_labels), len(pred_labels)))
    gi = {l: i for i, l in enumerate(gold_labels)}
    pj = {l: i for i, l in enumerate(pred_labels)}
    for g, p, c in pairs:
        mat[gi[g], pj[p]] = c

    fig3, ax3 = plt.subplots(figsize=(max(6, len(pred_labels) * 0.6), max(5, len(gold_labels) * 0.5)))
    im = ax3.imshow(mat, cmap="Oranges", aspect="auto")
    ax3.set_xticks(np.arange(len(pred_labels)))
    ax3.set_yticks(np.arange(len(gold_labels)))
    ax3.set_xticklabels(pred_labels, rotation=45, ha="right")
    ax3.set_yticklabels(gold_labels)
    ax3.set_xlabel("Predicted label")
    ax3.set_ylabel("Gold label")
    ax3.set_title("Label confusion (same surface text: gold → predicted)")
    for i in range(len(gold_labels)):
        for j in range(len(pred_labels)):
            v = mat[i, j]
            if v > 0:
                ax3.text(j, i, int(v), ha="center", va="center", color="black", fontsize=9)
    fig3.colorbar(im, ax=ax3, fraction=0.046, pad=0.04)
    fig3.tight_layout()
    if save_dir is not None:
        p3 = Path(save_dir) / "report_label_confusion_heatmap.png"
        fig3.savefig(p3, dpi=200, bbox_inches="tight")
        logger.info("Saved %s", p3)
    if show:
        plt.show()
    else:
        plt.close(fig3)


def write_evaluation_report(
    nlp: Language,
    val_examples: list[Example],
    val_docs: list[Any],
    report_dir: Path,
    *,
    show_plots: bool = False,
) -> dict[str, Any]:
    """
    One folder with report-ready tables and figures: metrics JSON/CSV, per-label plots,
    error aggregates JSON, error bar charts + confusion heatmap. Does not print examples.
    """
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    scores = evaluate(nlp, val_examples)
    export_metrics_json(scores, report_dir / "metrics.json")
    export_per_label_metrics_csv(scores, report_dir / "per_label_metrics.csv")
    plot_metrics_report_figures(scores, save_dir=report_dir, show=show_plots)

    errors = collect_errors(nlp, val_docs)
    stats = error_statistics(errors)
    n_docs = len(val_docs)
    stats["n_docs_evaluated"] = n_docs
    stats["doc_error_rate"] = round(len(errors) / n_docs, 6) if n_docs else 0.0
    export_error_statistics_json(stats, report_dir / "error_statistics.json")
    plot_error_analysis_figures(stats, save_dir=report_dir, show=show_plots)

    summary_path = report_dir / "report_summary.txt"
    ov = overall_metrics_dict(scores)
    lines = [
        "NER evaluation summary (for report)",
        "",
        "Overall (micro) entity metrics:",
        f"  Precision: {ov['precision']:.4f}",
        f"  Recall:    {ov['recall']:.4f}",
        f"  F1:        {ov['f1']:.4f}",
        "",
        f"Documents evaluated: {n_docs}",
        f"Documents with prediction errors: {len(errors)}",
        f"Doc-level error rate: {stats['doc_error_rate']:.4f}",
        "",
        "Span-level (set-difference) error counts:",
        f"  Missed entities (FN): {stats.get('n_span_missed', 0)}",
        f"  Extra entities (FP): {stats.get('n_span_extra', 0)}",
        "",
        "Files in this folder: metrics.json, per_label_metrics.csv, error_statistics.json,",
        "PNG figures (report_*.png).",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", summary_path)

    logger.info(
        "Evaluation report written to %s (metrics + error analysis figures)",
        report_dir,
    )
    return {"scores": scores, "error_stats": stats, "errors": errors}


def error_analysis(
    nlp: Language,
    docs: list[Any],
    n: int = 20,
    *,
    errors: list[tuple[str, set[tuple[str, str]], set[tuple[str, str]]]] | None = None,
    log: bool = False,
) -> list[tuple[str, set[tuple[str, str]], set[tuple[str, str]]]]:
    """
    Compare predicted entity sets to gold (normalized). Prints up to n mismatching examples.
    Pass ``errors`` from ``write_evaluation_report`` / ``collect_errors`` to avoid a second pass.
    """
    print("\n--- ERROR ANALYSIS ---\n")

    if errors is None:
        errors = collect_errors(nlp, docs)

    print(f"Total errors: {len(errors)} / {len(docs)}\n")

    for i, (text, pred, true) in enumerate(errors[:n]):
        print("=" * 80)
        print(f"Example {i + 1}")
        print("\nTEXT:\n", text)
        print("\nPREDICTED:")
        print(pred)
        print("\nTRUE:")
        print(true)
        print("\nMISSED (in TRUE but not predicted):")
        print(true - pred)
        print("\nEXTRA (predicted but not in TRUE):")
        print(pred - true)
        print("=" * 80)

    if log:
        logger.info("error_analysis: %s errors / %s docs", len(errors), len(docs))

    return errors


def plot_training_curves(
    history: list[tuple[int, float, float]],
    *,
    save_dir: Path | None = None,
    show: bool = True,
) -> None:
    """
    Plot training loss and validation F1 vs epoch (notebook section 17).
    history: list of (epoch_index, loss, f1).
    """
    import matplotlib.pyplot as plt

    epochs = [h[0] for h in history]
    losses = [h[1] for h in history]
    f1s = [h[2] for h in history]

    fig1, ax1 = plt.subplots()
    ax1.plot(epochs, losses)
    ax1.set_title("Training Loss")
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    fig1.tight_layout()
    if save_dir is not None:
        sd = Path(save_dir)
        sd.mkdir(parents=True, exist_ok=True)
        p = sd / "training_loss.png"
        fig1.savefig(p, dpi=150)
        logger.info("Saved %s", p)
    if show:
        plt.show()
    else:
        plt.close(fig1)

    fig2, ax2 = plt.subplots()
    ax2.plot(epochs, f1s)
    ax2.set_title("Validation F1 Score")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("F1")
    fig2.tight_layout()
    if save_dir is not None:
        sd = Path(save_dir)
        p = sd / "validation_f1.png"
        fig2.savefig(p, dpi=150)
        logger.info("Saved %s", p)
    if show:
        plt.show()
    else:
        plt.close(fig2)

    print("\nALL DONE ✅")
