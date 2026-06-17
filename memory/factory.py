"""Build a memory backend from environment variables.

    MEMORY_ENABLED=true|false        (default true)
    MEMORY_BACKEND=obsidian|supabase (default obsidian)

    # obsidian
    OBSIDIAN_VAULT_PATH=./memory_vault

    # supabase
    SUPABASE_URL=...
    SUPABASE_KEY=...            (service-role key; or SUPABASE_SERVICE_KEY)
    MEMORY_TABLE=memories
    EMBEDDINGS_PROVIDER=openai|hashing
"""

from __future__ import annotations

import os

from .base import MemoryStore
from .obsidian import ObsidianMemory


def memory_enabled() -> bool:
    return os.getenv("MEMORY_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def build_memory() -> MemoryStore:
    """Construct the configured backend. Raises on misconfiguration."""
    backend = os.getenv("MEMORY_BACKEND", "obsidian").strip().lower()

    if backend == "obsidian":
        vault = os.getenv("OBSIDIAN_VAULT_PATH", "./memory_vault")
        return ObsidianMemory(vault)

    if backend == "supabase":
        # Imported here so the common (obsidian) path never imports embeddings.
        from .embeddings import build_embeddings_from_env
        from .supabase_store import SupabaseMemory

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or ""
        return SupabaseMemory(
            url=url,
            key=key,
            embed=build_embeddings_from_env(),
            table=os.getenv("MEMORY_TABLE", "memories"),
        )

    raise ValueError(f"unknown MEMORY_BACKEND '{backend}' (expected obsidian|supabase)")
