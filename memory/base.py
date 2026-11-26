"""Cross-session memory for JARVIS — storage interface.

A ``MemoryStore`` lets JARVIS persist things worth remembering ("remember that
my garage code is 1234", facts learned mid-conversation) and recall them later,
across restarts. Two concrete backends implement this interface:

* :class:`memory.obsidian.ObsidianMemory` — markdown notes in a local vault,
  keyword/recency recall, zero external dependencies (fully offline).
* :class:`memory.supabase_store.SupabaseMemory` — Postgres + pgvector for
  semantic recall at scale.

Pick one with :func:`memory.factory.build_memory` (driven by env vars).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Timezone-aware UTC timestamp, second precision, ISO-8601."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class MemoryRecord:
    """One stored memory and (after a search) its relevance score."""

    id: str
    text: str
    created_at: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "created_at": self.created_at,
            "metadata": self.metadata,
            "score": round(self.score, 4),
        }


class MemoryStore(abc.ABC):
    """Common interface every memory backend implements."""

    @abc.abstractmethod
    def add(self, text: str, metadata: dict | None = None) -> MemoryRecord:
        """Persist a memory and return the stored record (with its id)."""

    @abc.abstractmethod
    def search(self, query: str, k: int = 5) -> list[MemoryRecord]:
        """Return up to ``k`` records most relevant to ``query``, best first."""

    @abc.abstractmethod
    def recent(self, k: int = 5) -> list[MemoryRecord]:
        """Return up to ``k`` most recently stored records, newest first."""

    @abc.abstractmethod
    def count(self) -> int:
        """Total number of stored memories."""
