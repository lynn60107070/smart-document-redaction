"""
Token-level NER CSV → augmented sentence-level dataset + spaCy DocBin export.

Default output directory is ``<repo>/data/processed/`` (override with ``--output-dir``).
Writes: spacy_redaction_data.json, spacy_redaction_data.jsonl, cleaned_sentence_level.csv,
cleaned_token_level.csv, and **redaction_train.spacy** (spaCy DocBin) unless you pass
``--no-docbin`` (e.g. spaCy init fails) or set ``SAVE_DOCBIN`` to False in config.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LABEL_MAP = {
    "per": "PERSON",
    "org": "ORGANIZATION",
    "geo": "LOCATION",
    "gpe": "LOCATION",
    "loc": "LOCATION",
    "tim": "DATETIME",
}

NER_LABELS = frozenset({"PERSON", "ORGANIZATION", "LOCATION", "DATE", "TIME"})

# Regex / pattern-based labels (synthetic samples + strict validation); same set as notebook.
REGEX_LABELS = frozenset(
    {
        "EMAIL",
        "PHONE",
        "CREDIT_CARD",
        "ID",
        "PASSPORT",
        "IP_ADDRESS",
        "URL_TOKEN",
        "MONEY",
        "PERCENT",
    }
)

BAD_LABEL_FIXES = {
    "red cross": "ORGANIZATION",
    "western sahara": "LOCATION",
}

DATE_KEYWORDS = [
    "january",
    "feb",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

NO_SPACE_BEFORE = {".", ",", "!", "?", ";", ":", "%", ")", "]", "}", "'s", "n't"}
NO_SPACE_AFTER = {"(", "[", "{", "$", "#", '"'}

TARGET_RATIOS = {
    "LOCATION": 1.0,
    "PERSON": 0.45,
    "ORGANIZATION": 0.40,
    "DATE": 0.40,
    "TIME": 0.25,
}

HARD_NEGATIVES = [
    ("email me the report", {"entities": []}),
    ("call me maybe", {"entities": []}),
    ("the word johnny is here", {"entities": []}),
    ("apple is tasty", {"entities": []}),
    ("may is a nice month", {"entities": []}),
    ("send the file asap", {"entities": []}),
    ("this is just a random sentence", {"entities": []}),
    ("contact support team", {"entities": []}),
]

# Allowed labels on exported examples (CoNLL-style NER + regex synthetics).
ALL_EXPORT_LABELS = frozenset(NER_LABELS | REGEX_LABELS)


def default_config() -> dict[str, Any]:
    return {
        # Mirrors notebook CONFIG. The notebook only used AUGMENT_CASE_VARIANTS and
        # AUGMENT_LOWERCASE_CONTEXT in code; other toggles are kept for parity / future use.
        "AUGMENT_CASE_VARIANTS": True,
        "AUGMENT_SINGLE_NAME_PERSON": True,
        "AUGMENT_LOWERCASE_CONTEXT": True,
        "AUGMENT_MISSING_REDACTION_LABELS": True,
        "MAX_SINGLE_NAME_SAMPLES": 4000,
        "SYNTHETIC_SAMPLES_PER_LABEL": {
            "PERSON": 250,
            "ORGANIZATION": 200,
            "LOCATION": 150,
            "GPE": 150,
            "DATE": 200,
            "TIME": 600,
        },
        "SAVE_DOCBIN": True,
        "DOCBIN_NAME": "redaction_train.spacy",
        "CLEANED_TOKEN_CSV_NAME": "cleaned_token_level.csv",
        "SENTENCE_CSV_NAME": "cleaned_sentence_level.csv",
        "SPACY_JSON_NAME": "spacy_redaction_data.json",
        "SPACY_JSONL_NAME": "spacy_redaction_data.jsonl",
        "REGEX_SAMPLES_ROUNDS": 30,
        "TIME_VARIANTS_N": 4000,
    }


# ---------------------------------------------------------------------------
# Loading & cleaning
# ---------------------------------------------------------------------------


def resolve_input_csv(repo_root: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        p = explicit.resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Input CSV not found: {p}")
        return p

    candidates = [
        repo_root / "data" / "raw" / "NER_raw.csv",
        repo_root / "data" / "raw" / "NER dataset.csv",
        repo_root / "data" / "raw" / "ner_dataset.csv",
        repo_root / "data" / "raw" / "ner.csv",
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(
        "No input CSV specified and none found at: " + ", ".join(str(c) for c in candidates)
    )


def load_token_dataframe(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="latin")
    df.columns = [c.strip() for c in df.columns]
    df.rename(
        columns={
            "Sentence #": "Sentence #",
            "Word": "Word",
            "POS": "POS",
            "Tag": "Tag",
        },
        inplace=True,
    )
    df["Sentence #"] = df["Sentence #"].ffill()
    return df


def clean_word(x: Any) -> str:
    if pd.isna(x):
        return ""
    x = str(x)
    x = x.replace("\u200b", "").replace("\xa0", " ")
    replacements = {"``": '"', "''": '"', "`": "'"}
    x = replacements.get(x, x)
    return x.strip()


def clean_tag(x: Any) -> str:
    if pd.isna(x):
        return "O"
    return str(x).strip().upper()


def clean_pos(x: Any) -> str:
    if pd.isna(x):
        return "UNK"
    return str(x).strip().upper()


def clean_tokens(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    rows_before = len(df)
    df = df.copy()
    df["Word"] = df["Word"].apply(clean_word)
    df["Tag"] = df["Tag"].apply(clean_tag)
    if "POS" in df.columns:
        df["POS"] = df["POS"].apply(clean_pos)
    df = df[df["Word"].str.len() > 0].copy()
    rows_after = len(df)
    return df, rows_before, rows_after


def split_tag(tag: Any) -> tuple[str, str]:
    tag = str(tag).strip().upper()
    if tag == "O":
        return "O", "O"
    if "-" not in tag:
        return "B", tag
    b, t = tag.split("-", 1)
    t = LABEL_MAP.get(t.lower(), t.upper())
    return b, t


def classify_datetime(text: str) -> str:
    t = text.lower()
    if re.search(r"\d{1,2}:\d{2}", t):
        return "TIME"
    if any(k in t for k in ["am", "pm"]):
        return "TIME"
    if any(k in t for k in DATE_KEYWORDS):
        return "DATE"
    if re.match(r"\d{4}-\d{2}-\d{2}", t):
        return "DATE"
    if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", t):
        return "DATE"
    if re.match(r"\d{4}", t):
        return "DATE"
    return "DATE"


def apply_label_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["BIO"], df["TYPE"] = zip(*df["Tag"].apply(split_tag))
    return df


def should_add_space(prev_token: str | None, token: str) -> bool:
    if prev_token is None:
        return False
    if token in NO_SPACE_BEFORE:
        return False
    if prev_token in NO_SPACE_AFTER:
        return False
    return True


def build_sentences_from_df(df: pd.DataFrame) -> list[tuple[str, dict]]:
    sentences: list[tuple[str, dict]] = []
    for _sid, group in tqdm(df.groupby("Sentence #"), desc="Building sentences"):
        words = group["Word"].tolist()
        bios = group["BIO"].tolist()
        types = group["TYPE"].tolist()

        text_parts: list[str] = []
        token_starts: list[int] = []
        token_ends: list[int] = []
        current_len = 0
        prev_tok: str | None = None

        for tok in words:
            tok = str(tok)
            if should_add_space(prev_tok, tok):
                text_parts.append(" ")
                current_len += 1
            token_starts.append(current_len)
            text_parts.append(tok)
            current_len += len(tok)
            token_ends.append(current_len)
            prev_tok = tok

        text = "".join(text_parts)

        entities: list[tuple[int, int, str]] = []
        current_start: int | None = None
        current_end: int | None = None
        current_type: str | None = None

        for i in range(len(words)):
            bio = bios[i]
            typ = types[i]
            start = token_starts[i]
            end = token_ends[i]

            if typ == "DATETIME":
                entity_text = text[start:end]
                typ = classify_datetime(entity_text)

            if bio == "B":
                if current_type is not None:
                    entities.append((current_start, current_end, current_type))
                current_start = start
                current_end = end
                current_type = typ
            elif bio == "I" and current_type == typ:
                current_end = end
            else:
                if current_type is not None:
                    entities.append((current_start, current_end, current_type))
                current_start = None
                current_end = None
                current_type = None

        if current_type is not None:
            entities.append((current_start, current_end, current_type))

        clean_entities = []
        for s, e, l in entities:
            if s < e and e <= len(text):
                clean_entities.append((s, e, l))

        sentences.append((text, {"entities": clean_entities}))

    return sentences


def clean_bad_annotations(
    sentences: list[tuple[str, dict]],
) -> list[tuple[str, dict]]:
    cleaned = []
    for text, ann in sentences:
        new_ents = []
        for s, e, l in ann["entities"]:
            entity_text = text[s:e].lower().strip()
            for key, fixed_label in BAD_LABEL_FIXES.items():
                if key in entity_text:
                    l = fixed_label
                    break
            if l in NER_LABELS:
                new_ents.append((s, e, l))
        cleaned.append((text, {"entities": new_ents}))
    return cleaned


# ---------------------------------------------------------------------------
# Augmentation
# ---------------------------------------------------------------------------


def transform_case(
    text: str, entities: list[tuple[int, int, str]], mode: str
) -> tuple[str, list[tuple[int, int, str]]]:
    if mode == "lower":
        new_text = text.lower()
    elif mode == "upper":
        new_text = text.upper()
    elif mode == "title":
        new_text = text.title()
    else:
        return text, entities
    return new_text, entities


def generate_noisy_person(name: str) -> list[str]:
    return [
        f"hey my name is {name.lower()}",
        f"pls contact {name.lower()} asap",
    ]


def augment_dataset(
    cleaned: list[tuple[str, dict]], config: dict[str, Any]
) -> list[tuple[str, dict]]:
    augmented: list[tuple[str, dict]] = []
    for text, ann in cleaned:
        entities = ann["entities"]
        augmented.append((text, {"entities": entities}))

        if config.get("AUGMENT_CASE_VARIANTS", True):
            for mode in ["lower", "upper", "title"]:
                new_text, new_entities = transform_case(text, entities, mode)
                augmented.append((new_text, {"entities": new_entities}))

        if config.get("AUGMENT_LOWERCASE_CONTEXT", True):
            for s, e, l in entities:
                if l == "PERSON":
                    name = text[s:e]
                    for noisy in generate_noisy_person(name):
                        start = noisy.find(name.lower())
                        if start != -1:
                            end = start + len(name)
                            augmented.append((noisy, {"entities": [(start, end, "PERSON")]}))

    augmented.extend(HARD_NEGATIVES)
    return augmented


def regex_sample(label: str, value: str) -> tuple[str, dict]:
    text = f"Sensitive: {value}"
    s = text.index(value)
    return (text, {"entities": [(s, s + len(value), label)]})


def generate_regex_samples(n: int) -> list[tuple[str, dict]]:
    samples: list[tuple[str, dict]] = []
    for _ in range(n):
        samples.extend(
            [
                regex_sample("EMAIL", f"user{random.randint(1, 999)}@example.com"),
                regex_sample(
                    "PHONE",
                    f"+974 {random.randint(3000, 7999)} {random.randint(1000, 9999)}",
                ),
                regex_sample(
                    "CREDIT_CARD",
                    f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-"
                    f"{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
                ),
                regex_sample(
                    "IP_ADDRESS",
                    f"{random.randint(1, 255)}.{random.randint(1, 255)}."
                    f"{random.randint(1, 255)}.{random.randint(1, 255)}",
                ),
                regex_sample("MONEY", f"${random.randint(10, 9999)}"),
                regex_sample("PERCENT", f"{random.randint(1, 100)}%"),
                regex_sample(
                    "URL_TOKEN",
                    f"https://api.test.com?token={random.randint(10000, 99999)}",
                ),
                regex_sample("ID", f"ID{random.randint(10000, 99999)}"),
                regex_sample("PASSPORT", f"A{random.randint(1000000, 9999999)}"),
            ]
        )
    return samples


def generate_time_variants(n: int) -> list[tuple[str, dict]]:
    templates = [
        "The meeting is at {t}.",
        "Call me at {t}.",
        "The event starts at {t}.",
        "The time is {t}.",
        "Arrival time: {t}.",
    ]
    time_values = [
        "10:30 AM",
        "14:45",
        "9 pm",
        "08:15 a.m.",
        "23:59",
        "12:00 PM",
    ]
    examples: list[tuple[str, dict]] = []
    for _ in range(n):
        t = random.choice(time_values)
        template = random.choice(templates)
        text = template.format(t=t)
        start = text.index(t)
        end = start + len(t)
        examples.append((text, {"entities": [(start, end, "TIME")]}))
    return examples


def validate_entities(text: str, ents: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    valid: list[tuple[int, int, str]] = []
    seen_spans: set[tuple[int, int, str]] = set()
    for s, e, l in ents:
        if not isinstance(s, int) or not isinstance(e, int):
            continue
        if s < 0 or e <= s or e > len(text):
            continue
        span_text = text[s:e].strip()
        if span_text == "":
            continue
        key = (s, e, l)
        if key not in seen_spans:
            seen_spans.add(key)
            valid.append((s, e, l))
    return valid


def deduplicate_examples(
    augmented: list[tuple[str, dict]],
) -> list[tuple[str, dict]]:
    final_data: list[tuple[str, dict]] = []
    seen_examples: set[tuple[str, tuple[tuple[int, int, str], ...]]] = set()
    for text, ann in augmented:
        ents = validate_entities(text, ann["entities"])
        key = (text, tuple(ents))
        if key not in seen_examples:
            seen_examples.add(key)
            final_data.append((text, {"entities": ents}))
    return final_data


def compute_label_counts(data: list[tuple[str, dict]]) -> Counter:
    counter: Counter = Counter()
    for _, ann in data:
        for _, _, l in ann["entities"]:
            counter[l] += 1
    return counter


def index_by_label(data: list[tuple[str, dict]]) -> dict[str, list[tuple[str, dict]]]:
    label_to_samples: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for item in data:
        labels = {l for _, _, l in item[1]["entities"]}
        for l in labels:
            label_to_samples[l].append(item)
    return label_to_samples


def auto_balance_dataset(
    data: list[tuple[str, dict]], target_ratios: dict[str, float]
) -> list[tuple[str, dict]]:
    label_counts = compute_label_counts(data)
    label_index = index_by_label(data)
    anchor_label = max(label_counts, key=label_counts.get)
    anchor_count = label_counts[anchor_label]
    logging.info("Auto-balance anchor: %s (%s)", anchor_label, anchor_count)

    new_data = list(data)
    for label, ratio in target_ratios.items():
        if label not in label_counts:
            continue
        target_count = int(anchor_count * ratio)
        current_count = label_counts[label]
        if current_count < target_count:
            needed = target_count - current_count
            samples = label_index[label]
            for _ in range(needed):
                new_data.append(random.choice(samples))
    return new_data


# ---------------------------------------------------------------------------
# Validation (optional strict mode)
# ---------------------------------------------------------------------------


def run_quality_checks(final_data: list[tuple[str, dict]], *, strict: bool) -> None:
    if not final_data:
        raise ValueError("Dataset is empty")

    invalid_spans = 0
    for text, ann in final_data:
        for start, end, _ in ann["entities"]:
            if not isinstance(start, int) or not isinstance(end, int):
                invalid_spans += 1
            elif start < 0 or end <= start or end > len(text):
                invalid_spans += 1
            elif text[start:end].strip() == "":
                invalid_spans += 1

    overlaps = 0
    for text, ann in final_data:
        spans = sorted(ann["entities"], key=lambda x: x[0])
        for i in range(len(spans) - 1):
            if spans[i][1] > spans[i + 1][0]:
                overlaps += 1

    invalid_labels: set[str] = set()
    for _, ann in final_data:
        for _, _, l in ann["entities"]:
            if l not in ALL_EXPORT_LABELS:
                invalid_labels.add(l)

    counter = compute_label_counts(final_data)
    if strict:
        if invalid_spans:
            raise ValueError(f"Invalid spans: {invalid_spans}")
        if overlaps:
            raise ValueError(f"Overlapping spans: {overlaps}")
        if invalid_labels:
            raise ValueError(f"Invalid labels: {invalid_labels}")
        if counter.get("TIME", 0) <= 1000:
            raise ValueError("Expected TIME count > 1000 in strict mode")
        lower_count = sum(1 for text, _ in final_data if text.islower())
        upper_count = sum(1 for text, _ in final_data if text.isupper())
        if lower_count == 0 or upper_count == 0:
            raise ValueError("Strict mode requires upper and lower case examples")
        noisy_patterns = ["hey", "pls", "asap", "contact"]
        noisy_count = sum(
            1 for text, _ in final_data if any(p in text.lower() for p in noisy_patterns)
        )
        if noisy_count == 0:
            raise ValueError("Strict mode requires noisy augmentation samples")
        hard_negs = sum(1 for _, ann in final_data if len(ann["entities"]) == 0)
        if hard_negs == 0:
            raise ValueError("Strict mode requires hard-negative (empty) examples")

    logging.info(
        "Quality summary: invalid_spans=%s overlaps=%s invalid_labels=%s examples=%s",
        invalid_spans,
        overlaps,
        invalid_labels or "none",
        len(final_data),
    )
    for k, v in counter.most_common():
        logging.info("  %s: %s", k, v)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_artifacts(
    final_data: list[tuple[str, dict]],
    token_df: pd.DataFrame | None,
    output_dir: Path,
    config: dict[str, Any],
    *,
    write_docbin: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_name = config["SPACY_JSON_NAME"]
    jsonl_name = config["SPACY_JSONL_NAME"]
    sentence_name = config["SENTENCE_CSV_NAME"]
    token_name = config["CLEANED_TOKEN_CSV_NAME"]
    docbin_name = config["DOCBIN_NAME"]

    json_path = output_dir / json_name
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    logging.info("Wrote %s", json_path)

    jsonl_path = output_dir / jsonl_name
    with jsonl_path.open("w", encoding="utf-8") as f:
        for text, ann in final_data:
            f.write(
                json.dumps({"text": text, "entities": ann["entities"]}, ensure_ascii=False)
                + "\n"
            )
    logging.info("Wrote %s", jsonl_path)

    sentence_rows = []
    for i, (text, ann) in enumerate(final_data, start=1):
        for s, e, l in ann["entities"]:
            sentence_rows.append(
                {
                    "example_id": i,
                    "text": text,
                    "entity_text": text[s:e],
                    "label": l,
                    "start": s,
                    "end": e,
                }
            )
    sentence_df = pd.DataFrame(sentence_rows)
    sentence_csv_path = output_dir / sentence_name
    sentence_df.to_csv(sentence_csv_path, index=False, encoding="utf-8")
    logging.info("Wrote %s", sentence_csv_path)

    if token_df is not None:
        token_csv_path = output_dir / token_name
        token_df.to_csv(token_csv_path, index=False, encoding="utf-8")
        logging.info("Wrote %s", token_csv_path)

    if write_docbin and config.get("SAVE_DOCBIN", True):
        import spacy
        from spacy.tokens import DocBin

        docbin_path = output_dir / docbin_name
        try:
            nlp = spacy.blank("en")
        except Exception as e:
            logging.error(
                "spaCy blank('en') failed (%s). Skip DocBin with --no-docbin or align "
                "spaCy with its dependencies (e.g. pydantic/confection versions).",
                e,
            )
            raise
        doc_bin = DocBin()
        skipped = 0
        for text, ann in final_data:
            doc = nlp.make_doc(text)
            spans = []
            for s, e, l in ann["entities"]:
                span = doc.char_span(s, e, label=l, alignment_mode="contract")
                if span is None:
                    span = doc.char_span(s, e, label=l, alignment_mode="expand")
                if span:
                    spans.append(span)
                else:
                    skipped += 1
            doc.ents = spans
            doc_bin.add(doc)
        doc_bin.to_disk(docbin_path)
        logging.info("Wrote %s (skipped char_spans=%s)", docbin_path, skipped)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    input_csv: Path,
    output_dir: Path,
    config: dict[str, Any],
    *,
    balance: bool = True,
    strict_validation: bool = False,
    write_docbin: bool = True,
    seed: int = 42,
) -> list[tuple[str, dict]]:
    random.seed(seed)
    np.random.seed(seed)

    logging.info("Loading %s", input_csv)
    df = load_token_dataframe(input_csv)
    df, rows_before, rows_after = clean_tokens(df)
    logging.info("Token rows: %s -> %s (dropped empty words: %s)", rows_before, rows_after, rows_before - rows_after)

    df = apply_label_columns(df)
    token_df = df.copy()

    label_counts = Counter(df["TYPE"])
    logging.info("Label distribution (TYPE): %s", dict(label_counts.most_common()))

    sentences = build_sentences_from_df(df)
    cleaned = clean_bad_annotations(sentences)

    augmented = augment_dataset(cleaned, config)
    augmented.extend(
        generate_regex_samples(config.get("REGEX_SAMPLES_ROUNDS", 30))
    )
    augmented.extend(
        generate_time_variants(config.get("TIME_VARIANTS_N", 4000))
    )

    final_data = deduplicate_examples(augmented)
    logging.info("After dedup: %s examples", len(final_data))

    if balance:
        final_data = auto_balance_dataset(final_data, TARGET_RATIOS)
        logging.info("After balancing: %s examples", len(final_data))

    run_quality_checks(final_data, strict=strict_validation)

    export_artifacts(final_data, token_df, output_dir, config, write_docbin=write_docbin)
    return final_data


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description="Preprocess NER token CSV into training artifacts.")
    p.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to token-level CSV (default: first match under data/raw/)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "data" / "processed",
        help="Directory for JSON, JSONL, CSV, DocBin",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--no-balance",
        action="store_true",
        help="Skip auto-balancing upsampling",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Run notebook-style assertions (needs full augmentation run)",
    )
    p.add_argument(
        "--no-docbin",
        action="store_true",
        help="Skip redaction_train.spacy (useful if spaCy init fails in your env)",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="DEBUG logging")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    repo_root = Path(__file__).resolve().parent.parent
    input_csv = resolve_input_csv(repo_root, args.input)
    config = default_config()

    run_pipeline(
        input_csv,
        args.output_dir.resolve(),
        config,
        balance=not args.no_balance,
        strict_validation=args.strict,
        write_docbin=not args.no_docbin,
        seed=args.seed,
    )
    logging.info("Done.")


if __name__ == "__main__":
    main()
