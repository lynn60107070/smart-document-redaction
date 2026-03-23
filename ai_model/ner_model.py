"""
Load a trained spaCy NER pipeline from disk. Entity detection (NER + regex, redaction)
lives in ``entity_detector``.

Pydantic v2 requires rebuilding spaCy's config schemas (forward refs to ``Language``)
before ``spacy.load`` / ``spacy.blank`` — see ``rebuild_spacy_pydantic_schemas``.
"""

from __future__ import annotations

from pathlib import Path

from spacy.language import Language
import spacy

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = _REPO_ROOT / "model" / "ner_model"

_schemas_rebuilt = False


def rebuild_spacy_pydantic_schemas() -> None:
    """
    Call once per process before ``spacy.load`` or ``spacy.blank`` when using Pydantic v2.
    Resolves forward references in ``ConfigSchemaNlp`` / ``ConfigSchemaInit`` / ``ConfigSchema``.
    """
    global _schemas_rebuilt
    if _schemas_rebuilt:
        return
    from spacy.schemas import ConfigSchema, ConfigSchemaInit, ConfigSchemaNlp
    from spacy.training import Example
    from spacy.vocab import Vocab

    ns = {"Language": Language, "Example": Example, "Vocab": Vocab}
    for schema in (ConfigSchemaNlp, ConfigSchemaInit, ConfigSchema):
        schema.model_rebuild(_types_namespace=ns)
    _schemas_rebuilt = True


def load_ner_model(path: str | Path | None = None) -> Language:
    """
    Load spaCy model from ``model/ner_model`` by default (repo layout).
    After training, point to ``model/ner_model/model-best`` if you saved there.
    """
    rebuild_spacy_pydantic_schemas()

    p = Path(path) if path is not None else DEFAULT_MODEL_PATH
    p = p.resolve()
    if not p.exists():
        raise FileNotFoundError(f"Model path not found: {p}")
    try:
        return spacy.load(p)
    except Exception as e:
        err = str(e)
        tname = type(e).__name__
        if (
            "ConfigSchemaNlp" in err
            or tname == "PydanticUserError"
            or "FieldInfo" in err
            or "type_" in err
        ):
            raise RuntimeError(
                "spaCy failed to load the model. If you already use a venv, try: "
                "pip install -U spacy pydantic\n\n"
                "Original error "
                f"({tname}): {e}"
            ) from e
        raise
