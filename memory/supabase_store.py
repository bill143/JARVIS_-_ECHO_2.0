"""Supabase + pgvector memory backend — semantic recall at scale.

Stores each memory as a row in a ``memories`` table with a vector ``embedding``
column; recall runs a cosine-similarity match via the ``match_memories`` SQL
function (see ``memory/schema.sql``). The Supabase client and the embedding call
are imported/invoked lazily so importing this module never requires the
``supabase`` package or network access.

STATUS: code-complete; RUNTIME-BLOCKED until a Supabase project + the schema in
``memory/schema.sql`` are provisioned and ``SUPABASE_URL`` / ``SUPABASE_KEY``
are set.
"""

from __future__ import annotations

import uuid

from .base import MemoryRecord, MemoryStore, utc_now_iso
from .embeddings import EmbeddingFunction


class SupabaseMemory(MemoryStore):
    def __init__(
        self,
        url: str,
        key: str,
        embed: EmbeddingFunction,
        table: str = "memories",
        match_fn: str = "match_memories",
    ) -> None:
        if not url or not key:
            raise ValueError("SupabaseMemory requires both url and key")
        self.url = url
        self.key = key
        self.embed = embed
        self.table = table
        self.match_fn = match_fn
        self._client = None

    def _db(self):
        if self._client is None:
            from supabase import create_client  # lazy import

            self._client = create_client(self.url, self.key)
        return self._client

    def add(self, text: str, metadata: dict | None = None) -> MemoryRecord:
        text = (text or "").strip()
        if not text:
            raise ValueError("cannot store an empty memory")
        record = MemoryRecord(
            id=uuid.uuid4().hex,
            text=text,
            created_at=utc_now_iso(),
            metadata=metadata or {},
        )
        self._db().table(self.table).insert(
            {
                "id": record.id,
                "content": record.text,
                "metadata": record.metadata,
                "embedding": self.embed(record.text),
                "created_at": record.created_at,
            }
        ).execute()
        return record

    def search(self, query: str, k: int = 5) -> list[MemoryRecord]:
        embedding = self.embed(query or "")
        resp = self._db().rpc(
            self.match_fn,
            {"query_embedding": embedding, "match_count": max(1, k)},
        ).execute()
        rows = resp.data or []
        return [self._row_to_record(row) for row in rows]

    def recent(self, k: int = 5) -> list[MemoryRecord]:
        resp = (
            self._db()
            .table(self.table)
            .select("id, content, metadata, created_at")
            .order("created_at", desc=True)
            .limit(max(1, k))
            .execute()
        )
        return [self._row_to_record(row) for row in (resp.data or [])]

    def count(self) -> int:
        resp = self._db().table(self.table).select("id", count="exact").execute()
        return resp.count or 0

    @staticmethod
    def _row_to_record(row: dict) -> MemoryRecord:
        return MemoryRecord(
            id=str(row.get("id", "")),
            text=row.get("content", ""),
            created_at=str(row.get("created_at", "")),
            metadata=row.get("metadata") or {},
            score=float(row.get("similarity", 0.0) or 0.0),
        )
