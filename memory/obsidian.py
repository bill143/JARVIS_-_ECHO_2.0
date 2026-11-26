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
        records = []
        for path in self.vault.glob("*.md"):
            rec = self._read(path)
            if rec is not None:
                records.append(rec)
        return records

    def count(self) -> int:
        return sum(1 for _ in self.vault.glob("*.md"))

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
