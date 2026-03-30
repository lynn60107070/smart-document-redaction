"""
Tests for NER loading (``ai_model.ner_model``) and hybrid detection (``ai_model.entity_detector``).

``detect_entities`` / ``redact`` are exercised with a tiny fake ``nlp`` object (no disk model,
no ``spacy.blank``), so tests stay fast and stable across Pydantic / spaCy builds. A separate
case loads the real pipeline when ``model/ner_model`` is present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ai_model.entity_detector import (
    REGEX_PATTERNS,
    detect_entities,
    detect_regex,
    merge_entities,
    redact,
)
from ai_model.ner_model import DEFAULT_MODEL_PATH, load_ner_model


class _FakeEnt:
    __slots__ = ("text", "label_", "start_char", "end_char")

    def __init__(self, text: str, label_: str, start_char: int, end_char: int) -> None:
        self.text = text
        self.label_ = label_
        self.start_char = start_char
        self.end_char = end_char


class _FakeDoc:
    __slots__ = ("ents",)

    def __init__(self, ents: list[_FakeEnt]) -> None:
        self.ents = ents


class FakeNlp:
    """
    Mimics ``Language.__call__`` + ``Doc.ents`` for deterministic tests.
    Each ``(literal, label)`` pair is found with ``str.find`` (all non-overlapping occurrences).
    """

    def __init__(self, literals: list[tuple[str, str]]) -> None:
        self._literals = literals

    def __call__(self, text: str) -> _FakeDoc:
        ents: list[_FakeEnt] = []
        for literal, label in self._literals:
            start = 0
            while True:
                i = text.find(literal, start)
                if i < 0:
                    break
                ents.append(_FakeEnt(literal, label, i, i + len(literal)))
                start = i + len(literal)
        ents.sort(key=lambda e: (e.start_char, e.end_char))
        return _FakeDoc(ents)


@pytest.fixture
def nlp_sample() -> FakeNlp:
    return FakeNlp([("John Doe", "PERSON"), ("Qatar", "GPE")])


def test_detect_regex_email_matches_project_pattern():
    # Local part uses only \w, dot, hyphen (see REGEX_PATTERNS) — no "+"
    text = "Reach me at user.name@example.co.uk today."
    found = detect_regex(text)
    emails = [e for e in found if e["label"] == "EMAIL"]
    assert len(emails) == 1
    assert emails[0]["text"] == "user.name@example.co.uk"
    assert text[emails[0]["start"] : emails[0]["end"]] == emails[0]["text"]


def test_detect_regex_phone_like_sequence():
    text = "Call 15551234567 or wait."
    found = detect_regex(text)
    phones = [e for e in found if e["label"] == "PHONE"]
    assert phones, "Expected PHONE regex to match a long digit run"
    assert all(e["start"] < e["end"] for e in found)


def test_merge_entities_prefers_non_overlapping_in_order():
    ner = [{"text": "A", "label": "X", "start": 0, "end": 1}]
    regex = [{"text": "B", "label": "Y", "start": 2, "end": 3}]
    merged = merge_entities(ner, regex)
    assert merged == ner + regex


def test_merge_entities_drops_overlap_after_first_span():
    first = {"text": "foo", "label": "A", "start": 0, "end": 10}
    overlap = {"text": "bar", "label": "B", "start": 5, "end": 8}
    merged = merge_entities([first], [overlap])
    assert merged == [first]


def test_detect_entities_combines_fake_ner_and_regex(nlp_sample: FakeNlp):
    text = "John Doe in Qatar, email: john@gmail.com"
    ents = detect_entities(nlp_sample, text)
    by_label = {e["label"]: e["text"] for e in ents}
    assert by_label.get("PERSON") == "John Doe"
    assert by_label.get("GPE") == "Qatar"
    assert by_label.get("EMAIL") == "john@gmail.com"


def test_detect_entities_skips_stopword_and_pure_digit_spans():
    nlp = FakeNlp([("email", "MISC"), ("12345", "CARDINAL")])
    text = "email and 12345 here"
    ents = detect_entities(nlp, text)
    texts = {e["text"] for e in ents}
    assert "email" not in texts
    assert "12345" not in texts


def test_redact_right_to_left_preserves_indices():
    nlp = FakeNlp([("Jane", "PERSON")])
    text = "Jane met Jane."
    out = redact(nlp, text)
    assert "Jane" not in out
    assert out.count("[REDACTED_PERSON]") == 2


@pytest.mark.parametrize(
    "user_text",
    [
        "Ping me at dev@company.org",
        "ID ABC123XYZ and phone 5551234567890",
        "No entities here really",
    ],
)
def test_user_provided_style_strings_structure(user_text: str, nlp_sample: FakeNlp):
    """User-style input always yields well-formed entity dicts (offsets match the source string)."""
    ents = detect_entities(nlp_sample, user_text)
    for e in ents:
        assert set(e.keys()) == {"text", "label", "start", "end"}
        assert isinstance(e["text"], str)
        assert isinstance(e["label"], str)
        assert 0 <= e["start"] < e["end"] <= len(user_text)
        assert user_text[e["start"] : e["end"]] == e["text"]


def test_load_ner_model_missing_path_raises(tmp_path: Path):
    missing = tmp_path / "no_model_here"
    with pytest.raises(FileNotFoundError, match="Model path not found"):
        load_ner_model(missing)


def test_regex_patterns_cover_expected_labels():
    assert set(REGEX_PATTERNS) >= {"EMAIL", "PHONE", "CREDIT_CARD", "ID"}


def test_default_trained_model_loads_and_detects_email():
    """Runs when ``model/ner_model`` exists; otherwise skipped."""
    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip(f"Default model path missing: {DEFAULT_MODEL_PATH}")
    nlp = load_ner_model()
    text = "Send files to reviewer@university.edu before Friday."
    ents = detect_entities(nlp, text)
    labels = {e["label"] for e in ents}
    assert "EMAIL" in labels
    assert any(e["text"] == "reviewer@university.edu" for e in ents)


def test_detect_entities_accepts_real_spacy_nlp_if_model_present():
    """Smoke-test the same API path the API uses (``Language`` instance from disk)."""
    if not DEFAULT_MODEL_PATH.exists():
        pytest.skip(f"Default model path missing: {DEFAULT_MODEL_PATH}")
    nlp: Any = load_ner_model()
    ents = detect_entities(nlp, "Nothing special")
    assert isinstance(ents, list)
