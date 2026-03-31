"""
Ephemeral PDF storage for the API.

Uploads and redacted outputs are written under the OS temp directory (see
``TempDocumentStore``). Metadata lives in memory; binary files are removed when
entries pass ``SESSION_TTL_SECONDS`` (1 hour) and cleanup runs on the next
mutating operation. There is no long-term database.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict
from uuid import uuid4


SESSION_TTL_SECONDS = 60 * 60


@dataclass
class StoredDocument:
    document_id: str
    filename: str
    pdf_path: Path
    created_at: float


@dataclass
class StoredOutput:
    token: str
    filename: str
    pdf_path: Path
    created_at: float


class TempDocumentStore:
    """Thread-safe store for uploaded PDFs and redacted PDF outputs on disk."""

    def __init__(self) -> None:
        self._root = Path(tempfile.gettempdir()) / "smart_redaction_api"
        self._root.mkdir(parents=True, exist_ok=True)
        self._documents: Dict[str, StoredDocument] = {}
        self._outputs: Dict[str, StoredOutput] = {}
        self._lock = Lock()

    def _cleanup_expired(self) -> None:
        """Drop in-memory keys and unlink files older than ``SESSION_TTL_SECONDS``."""
        cutoff = time.time() - SESSION_TTL_SECONDS

        expired_docs = [
            key for key, item in self._documents.items() if item.created_at < cutoff
        ]
        for key in expired_docs:
            item = self._documents.pop(key)
            item.pdf_path.unlink(missing_ok=True)

        expired_outputs = [
            key for key, item in self._outputs.items() if item.created_at < cutoff
        ]
        for key in expired_outputs:
            item = self._outputs.pop(key)
            item.pdf_path.unlink(missing_ok=True)

    def save_document(self, filename: str, data: bytes) -> StoredDocument:
        with self._lock:
            self._cleanup_expired()
            document_id = uuid4().hex
            pdf_path = self._root / f"{document_id}.pdf"
            pdf_path.write_bytes(data)
            stored = StoredDocument(
                document_id=document_id,
                filename=filename,
                pdf_path=pdf_path,
                created_at=time.time(),
            )
            self._documents[document_id] = stored
            return stored

    def get_document(self, document_id: str) -> StoredDocument | None:
        with self._lock:
            self._cleanup_expired()
            return self._documents.get(document_id)

    def save_output(self, filename: str, data: bytes) -> StoredOutput:
        with self._lock:
            self._cleanup_expired()
            token = uuid4().hex
            pdf_path = self._root / f"{token}.pdf"
            pdf_path.write_bytes(data)
            stored = StoredOutput(
                token=token,
                filename=filename,
                pdf_path=pdf_path,
                created_at=time.time(),
            )
            self._outputs[token] = stored
            return stored

    def get_output(self, token: str) -> StoredOutput | None:
        with self._lock:
            self._cleanup_expired()
            return self._outputs.get(token)
