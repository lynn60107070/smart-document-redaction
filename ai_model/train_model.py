"""
Train spaCy NER on a DocBin (same logic as ``notebooks/train_model.ipynb``).
Uses ``evaluation`` for metrics / plots / error analysis; ``entity_detector`` for post-train demo.

All run artifacts (training curves, metrics CSV/JSON, report figures) go under one folder:
see ``--artifacts-dir`` (default: ``model/ner_model/artifacts``).
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import sys
import time
from datetime import timedelta
from pathlib import Path

# Allow `python ai_model/train_model.py` from repo root
_AI_DIR = str(Path(__file__).resolve().parent)
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)

from spacy.language import Language
from spacy.tokens import DocBin
from spacy.training import Example
from spacy.util import fix_random_seed, minibatch

import spacy

from evaluation import (
    error_analysis,
    evaluate,
    log_metrics,
    plot_training_curves,
    print_metrics,
    write_evaluation_report,
)
from entity_detector import demo as entity_demo
from ner_model import rebuild_spacy_pydantic_schemas

_REPO_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def docs_to_examples(nlp: Language, docs: list) -> list[Example]:
    return [
        Example.from_dict(
            nlp.make_doc(doc.text),
            {"entities": [(ent.start_char, ent.end_char, ent.label_) for ent in doc.ents]},
        )
        for doc in docs
    ]


def train(
    *,
    train_path: Path,
    best_model_dir: Path,
    pretrained: str = "en_core_web_lg",
    n_epochs: int = 8,
    batch_size: int = 32,
    dropout: float = 0.2,
    val_fraction: float = 0.2,
    seed: int = 42,
    artifacts_dir: Path | None = None,
    show_plots: bool = False,
    error_analysis_n: int = 20,
    run_demo: bool = False,
    no_report: bool = False,
) -> tuple[Path, list[tuple[int, float, float]]]:
    rebuild_spacy_pydantic_schemas()

    fix_random_seed(seed)
    random.seed(seed)

    train_path = train_path.resolve()
    if not train_path.is_file():
        raise FileNotFoundError(f"DocBin not found: {train_path}")

    nlp_blank = spacy.blank("en")
    doc_bin = DocBin().from_disk(str(train_path))
    docs = list(doc_bin.get_docs(nlp_blank.vocab))
    logger.info("Loaded docs: %s", len(docs))

    random.shuffle(docs)
    split = int((1.0 - val_fraction) * len(docs))
    train_docs = docs[:split]
    val_docs = docs[split:]
    logger.info("Train: %s | Validation: %s", len(train_docs), len(val_docs))

    train_examples = docs_to_examples(nlp_blank, train_docs)
    val_examples = docs_to_examples(nlp_blank, val_docs)
    logger.info("Examples — train: %s | val: %s", len(train_examples), len(val_examples))

    nlp = spacy.load(pretrained)
    if "ner" in nlp.pipe_names:
        nlp.remove_pipe("ner")
    ner = nlp.add_pipe("ner")

    labels: set[str] = set()
    for doc in train_docs:
        for ent in doc.ents:
            labels.add(ent.label_)
    for label in labels:
        ner.add_label(label)

    nlp.initialize()
    logger.info("NER labels: %s", labels)

    other_pipes = [p for p in nlp.pipe_names if p != "ner"]
    best_f1 = -1.0
    history: list[tuple[int, float, float]] = []

    logger.info("========== TRAINING START ==========")
    logger.info("Epochs: %s | batch: %s | dropout: %s", n_epochs, batch_size, dropout)

    start_training_time = time.time()

    with nlp.disable_pipes(*other_pipes):
        for epoch in range(n_epochs):
            epoch_start = time.time()
            random.shuffle(train_examples)
            losses = {}

            batches = minibatch(train_examples, size=batch_size)
            total_batches = math.ceil(len(train_examples) / batch_size)

            logger.info("Epoch %s/%s | batches: %s", epoch + 1, n_epochs, total_batches)

            batch_start_time = time.time()
            for i, batch in enumerate(batches):
                nlp.update(batch, drop=dropout, losses=losses)

                if (i + 1) % 100 == 0 or (i + 1) == total_batches:
                    elapsed = time.time() - batch_start_time
                    avg_time = elapsed / (i + 1)
                    remaining_batches = total_batches - (i + 1)
                    eta = remaining_batches * avg_time
                    logger.info(
                        "Batch %s/%s | avg batch: %.2fs | ETA: %s",
                        i + 1,
                        total_batches,
                        avg_time,
                        timedelta(seconds=int(eta)),
                    )

            epoch_time = time.time() - epoch_start
            loss_ner = losses.get("ner", 0.0)
            logger.info(
                "Epoch %s done | loss: %s | epoch time: %s",
                epoch + 1,
                loss_ner,
                timedelta(seconds=int(epoch_time)),
            )

            scores = evaluate(nlp, val_examples)
            f1 = float(scores["ents_f"])
            print_metrics(scores)
            log_metrics(scores, prefix=f"epoch {epoch + 1}")

            history.append((epoch, float(loss_ner), f1))

            if f1 > best_f1:
                best_f1 = f1
                best_model_dir.mkdir(parents=True, exist_ok=True)
                nlp.to_disk(best_model_dir)
                logger.info("Saved BEST model to %s", best_model_dir)

            elapsed_total = time.time() - start_training_time
            avg_epoch_time = elapsed_total / (epoch + 1)
            remaining_epochs = n_epochs - (epoch + 1)
            total_eta = remaining_epochs * avg_epoch_time
            logger.info(
                "Progress — elapsed: %s | avg epoch: %s | remaining epochs: %s | ETA: %s",
                timedelta(seconds=int(elapsed_total)),
                timedelta(seconds=int(avg_epoch_time)),
                remaining_epochs,
                timedelta(seconds=int(total_eta)),
            )

    logger.info("========== TRAINING COMPLETE ==========")
    logger.info("Best validation F1: %.4f", best_f1)

    nlp_best = spacy.load(best_model_dir)
    logger.info("Loaded best model from %s", best_model_dir)

    out = Path(artifacts_dir) if artifacts_dir is not None else None
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        logger.info("Artifacts (plots, metrics, report): %s", out.resolve())

    err_list = None
    if not no_report and out is not None:
        rep = write_evaluation_report(
            nlp_best,
            val_examples,
            val_docs,
            out,
            show_plots=show_plots,
        )
        err_list = rep["errors"]
    elif not no_report and out is None:
        logger.warning("No artifacts_dir set; skipping evaluation report files.")
    error_analysis(nlp_best, val_docs, n=error_analysis_n, errors=err_list)

    plot_training_curves(history, save_dir=out, show=show_plots)

    if run_demo:
        entity_demo(nlp_best)

    return best_model_dir, history


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train spaCy NER from DocBin (notebook parity).")
    p.add_argument(
        "--train-path",
        type=Path,
        default=_REPO_ROOT / "data" / "processed" / "redaction_train.spacy",
        help="Path to redaction_train.spacy DocBin",
    )
    p.add_argument(
        "--best-dir",
        type=Path,
        default=_REPO_ROOT / "model" / "ner_model" / "model-best",
        help="Directory to save best model (nlp.to_disk)",
    )
    p.add_argument(
        "--pretrained",
        type=str,
        default="en_core_web_lg",
        help="spaCy pretrained pipeline to fine-tune",
    )
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--val-fraction", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--artifacts-dir",
        type=Path,
        default=_REPO_ROOT / "model" / "ner_model" / "artifacts",
        help="Single folder for training curves, metrics JSON/CSV, and report figures",
    )
    p.add_argument(
        "--show-plots",
        action="store_true",
        help="Show matplotlib windows (figures are still saved under --artifacts-dir)",
    )
    p.add_argument("--error-analysis-n", type=int, default=20)
    p.add_argument(
        "--demo",
        action="store_true",
        help="Run hybrid NER+regex demo strings after training",
    )
    p.add_argument(
        "--no-report",
        action="store_true",
        help="Skip evaluation report files (metrics/CSV/error figures); training curves still saved",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    train(
        train_path=args.train_path,
        best_model_dir=args.best_dir,
        pretrained=args.pretrained,
        n_epochs=args.epochs,
        batch_size=args.batch_size,
        dropout=args.dropout,
        val_fraction=args.val_fraction,
        seed=args.seed,
        artifacts_dir=args.artifacts_dir,
        show_plots=args.show_plots,
        error_analysis_n=args.error_analysis_n,
        run_demo=args.demo,
        no_report=args.no_report,
    )


if __name__ == "__main__":
    main()
