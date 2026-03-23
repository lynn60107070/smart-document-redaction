"""
Hybrid entity detection: spaCy NER spans + regex patterns, merge, and redaction.

Uses a loaded ``Language`` pipeline from ``ner_model.load_ner_model``; this module
does not load weights itself.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import warnings
warnings.filterwarnings("ignore")


from spacy.language import Language

# Allow `python ai_model/entity_detector.py` from repo root
_AI_DIR = str(Path(__file__).resolve().parent)
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)

REGEX_PATTERNS = {
    "EMAIL": r"\b[\w\.-]+@[\w\.-]+\.\w+\b",
    "PHONE": r"\b(?:\+?\d{1,3})?\d{8,15}\b",
    "CREDIT_CARD": r"\b\d{13,16}\b",
    "ID": r"\b[A-Z0-9]{6,12}\b",
}

STOPWORDS = {"email", "contact"}


def detect_regex(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for label, pattern in REGEX_PATTERNS.items():
        for m in re.finditer(pattern, text):
            results.append(
                {
                    "text": m.group(),
                    "label": label,
                    "start": m.start(),
                    "end": m.end(),
                }
            )
    return results


def merge_entities(
    ner: list[dict[str, Any]], regex: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    all_e = ner + regex
    all_e = sorted(all_e, key=lambda x: (x["start"], -x["end"]))
    final: list[dict[str, Any]] = []
    last_end = -1
    for e in all_e:
        if e["start"] >= last_end:
            final.append(e)
            last_end = e["end"]
    return final


def detect_entities(nlp: Language, text: str) -> list[dict[str, Any]]:
    doc = nlp(text)
    ner_entities: list[dict[str, Any]] = []
    for ent in doc.ents:
        if ent.text.lower() in STOPWORDS:
            continue
        if ent.text.isdigit():
            continue
        ner_entities.append(
            {
                "text": ent.text,
                "label": ent.label_.upper(),
                "start": ent.start_char,
                "end": ent.end_char,
            }
        )
    regex_entities = detect_regex(text)
    return merge_entities(ner_entities, regex_entities)


def redact(nlp: Language, text: str) -> str:
    ents = detect_entities(nlp, text)
    for e in sorted(ents, key=lambda x: x["start"], reverse=True):
        text = text[: e["start"]] + f"[REDACTED_{e['label']}]" + text[e["end"] :]
    return text


def demo(nlp: Language) -> None:
    """Notebook sample strings."""
    samples = [
        "John lives in Qatar. Email: john@gmail.com",
        "my name is ahmed and my card is 1234567890123456",
        "Sarah paid 500 dollars",
        "Contact me at 5551234567",
    ]
    for s in samples:
        print("\nTEXT:", s)
        print("ENTITIES:", detect_entities(nlp, s))
        print("REDACTED:", redact(nlp, s))


if __name__ == "__main__":
    import argparse

    from ner_model import load_ner_model

    ap = argparse.ArgumentParser(
        description="Load NER model and run hybrid entity detection (NER + regex)."
    )
    ap.add_argument(
        "--model",
        type=Path,
        default=None,
        help="spaCy model dir (default: model/ner_model; use model/ner_model/model-best after training)",
    )
    ap.add_argument(
        "-t",
        "--text",
        type=str,
        default=None,
        help='Your sentence to test, e.g. --text "John lives in Doha, email: j@x.com"',
    )
    ap.add_argument(
        "--demo",
        action="store_true",
        help="Run built-in sample strings instead of --text",
    )
    args = ap.parse_args()
    nlp = load_ner_model(args.model)

    if args.text is not None:
        print("TEXT:", args.text)
        print("ENTITIES:", detect_entities(nlp, args.text))
        print("REDACTED:", redact(nlp, args.text))
    elif args.demo:
        demo(nlp)
    else:
        ap.print_help()
        print(
            "\nExample: python entity_detector.py -t \"Contact me at 555-1234 or a@b.com\"\n"
            "Or:       python entity_detector.py --demo"
        )
