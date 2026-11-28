"""Obsidian-vault memory backend — markdown notes, offline, dependency-free.

Each memory is a single markdown file with YAML-style frontmatter:

    ---
    id: 0f2c...
    created_at: 2026-06-17T02:00:00+00:00
    tags: garage, codes
    source: voice
    ---
    The garage door code is 1234.

The vault is just a directory, so it's readable/editable in Obsidian (or any
editor) and survives restarts. Recall uses term-frequency keyword scoring with a
mild recency tiebreak — good enough for personal-assistant memory and entirely
local (no embeddings, no network). Uses only the standard library.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from .base import MemoryRecord, MemoryStore, utc_now_iso

_WORD = re.compile(r"[a-z0-9]+")
_RESERVED = {"id", "created_at"}


def _tokenize(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class ObsidianMemory(MemoryStore):
    def __init__(self, vault_path: str | os.PathLike) -> None:
        self.vault = Path(vault_path)
        self.vault.mkdir(parents=True, exist_ok=True)

    # ---- writing ----
    def add(self, text: str, metadata: dict | None = None) -> MemoryRecord:
        text = (text or "").strip()
        if not text:
            raise ValueError("cannot store an empty memory")
        metadata = {str(k): str(v) for k, v in (metadata or {}).items() if k not in _RESERVED}
        record = MemoryRecord(
            id=uuid.uuid4().hex,
            text=text,
            created_at=utc_now_iso(),
            metadata=metadata,
        )
        self._write(record)
        return record

    def _write(self, record: MemoryRecord) -> None:
        lines = ["---", f"id: {record.id}", f"created_at: {record.created_at}"]
        for key, value in record.metadata.items():
            lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")
        lines.append(record.text)
        lines.append("")
        path = self.vault / f"{record.created_at[:10]}-{record.id[:8]}.md"
        path.write_text("\n".join(lines), encoding="utf-8")

    def _path_for(self, record_id: str) -> Path | None:
        for path in self.vault.glob(f"*-{record_id[:8]}.md"):
            rec = self._read(path)
            if rec is not None and rec.id == record_id and _is_jarvis_memory(rec, path):
                return path
        return None

    # ---- editing (dashboard Facts tab) ----
    def update(self, record_id: str, text: str) -> MemoryRecord:
        """Replace a memory's text, keeping its id, timestamp and metadata."""
        text = (text or "").strip()
        if not text:
            raise ValueError("cannot store an empty memory")
        path = self._path_for(record_id)
        if path is None:
            raise KeyError(record_id)
        current = self._read(path)
        updated = MemoryRecord(id=current.id, text=text, created_at=current.created_at, metadata=current.metadata)
        self._write(updated)
        return updated

    def delete(self, record_id: str) -> None:
        """Remove a memory note written by JARVIS (never touches other notes)."""
        path = self._path_for(record_id)
        if path is None:
            raise KeyError(record_id)
        path.unlink()

    # ---- reading ----
    def _read(self, path: Path) -> MemoryRecord | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return None
        meta: dict[str, str] = {}
        body = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) == 3:
                _, front, body = parts
                for line in front.strip().splitlines():
                    if ":" in line:
                        key, _, value = line.partition(":")
                        meta[key.strip()] = value.strip()
        rec_id = meta.pop("id", path.stem)
        created_at = meta.pop("created_at", "")
        return MemoryRecord(
            id=rec_id,
            text=body.strip(),
            created_at=created_at,
            metadata=meta,
        )

    def _all(self) -> list[MemoryRecord]:
        """JARVIS's own memories only.

        The vault is usually a real Obsidian vault shared with the user's notes
        (Obsidian's "Welcome.md", drafts, empty notes). Only notes written by
        ``add`` count: they always carry ``id`` + a parseable ``created_at`` in
        their frontmatter and a non-empty body.
        """
        records = []
        for path in self.vault.glob("*.md"):
            rec = self._read(path)
            if rec is not None and _is_jarvis_memory(rec, path):
                records.append(rec)
        return records

    def count(self) -> int:
        return len(self._all())

    def recent(self, k: int = 5) -> list[MemoryRecord]:
        records = self._all()
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[: max(0, k)]

    def search(self, query: str, k: int = 5) -> list[MemoryRecord]:
        query_terms = _tokenize(query)
        if not query_terms:
            return self.recent(k)
        wanted = set(query_terms)
        scored: list[MemoryRecord] = []
        for rec in self._all():
            doc_terms = _tokenize(rec.text + " " + " ".join(rec.metadata.values()))
            if not doc_terms:
                continue
            overlap = sum(1 for t in doc_terms if t in wanted)
            if overlap == 0:
                continue
            # TF score normalized by document length, so short exact hits rank
            # above long rambling notes that merely mention the term.
            rec.score = overlap / (len(doc_terms) ** 0.5)
            scored.append(rec)
        # Primary: score. Tiebreak: recency.
        scored.sort(key=lambda r: (r.score, r.created_at), reverse=True)
        return scored[: max(0, k)]


def _is_jarvis_memory(rec: MemoryRecord, path: Path) -> bool:
    """True for notes written by ``ObsidianMemory.add``; False for vault boilerplate.

    ``add`` always writes frontmatter ``id`` (different from the file stem, which
    is ``<date>-<id8>``) and an ISO ``created_at``. Obsidian's Welcome.md and the
    user's own notes have neither, so they never surface as JARVIS "facts".
    """
    from datetime import datetime  # noqa: PLC0415

    if not rec.text.strip() or rec.id == path.stem or not rec.created_at:
        return False
    try:
        datetime.fromisoformat(rec.created_at)
    except ValueError:
        return False
    return True
