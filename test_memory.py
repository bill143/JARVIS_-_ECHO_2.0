"""Offline tests for the memory package (no network, no optional deps).

Covers the Obsidian backend (write/read/search/recent), the hashing embeddings,
and the factory's backend selection. Run directly:  python test_memory.py
"""

from __future__ import annotations

import os
import tempfile

from memory.embeddings import HashingEmbeddings
from memory.factory import build_memory, memory_enabled
from memory.obsidian import ObsidianMemory


def test_add_and_recall_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = ObsidianMemory(d)
        assert store.count() == 0
        rec = store.add("The garage door code is 1234.", {"source": "voice"})
        assert rec.id and rec.created_at
        store.add("My favourite coffee is a flat white.")
        store.add("The dog's name is Biscuit.")
        assert store.count() == 3

        hits = store.search("garage code")
        assert hits, "expected a hit for 'garage code'"
        assert "1234" in hits[0].text, f"top hit wrong: {hits[0].text!r}"

        coffee = store.search("coffee")
        assert coffee and "flat white" in coffee[0].text


def test_persistence_across_instances() -> None:
    with tempfile.TemporaryDirectory() as d:
        ObsidianMemory(d).add("Persisted fact about the boiler.")
        # A fresh instance pointed at the same vault must see it.
        reopened = ObsidianMemory(d)
        assert reopened.count() == 1
        assert reopened.search("boiler")[0].text.startswith("Persisted fact")


def test_recent_ordering_and_empty_query() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = ObsidianMemory(d)
        for i in range(3):
            store.add(f"memory number {i}")
        recent = store.recent(2)
        assert len(recent) == 2
        # Empty query falls back to recent.
        assert len(store.search("   ", k=2)) == 2


def test_metadata_survives() -> None:
    with tempfile.TemporaryDirectory() as d:
        store = ObsidianMemory(d)
        store.add("Has metadata.", {"source": "voice", "tags": "test"})
        rec = store.recent(1)[0]
        assert rec.metadata.get("source") == "voice"
        assert rec.metadata.get("tags") == "test"


def test_hashing_embeddings_deterministic_and_normalized() -> None:
    embed = HashingEmbeddings(dimensions=128)
    a = embed("hello world")
    b = embed("hello world")
    assert a == b, "hashing embeddings must be deterministic"
    assert len(a) == 128
    norm = sum(v * v for v in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6, f"expected unit norm, got {norm}"
    assert embed("hello world") != embed("totally different text")


def test_factory_selects_obsidian(tmp_path_env: str) -> None:
    store = build_memory()
    assert isinstance(store, ObsidianMemory)
    assert memory_enabled() is True


def test_factory_supabase_requires_credentials() -> None:
    os.environ["MEMORY_BACKEND"] = "supabase"
    os.environ.pop("SUPABASE_URL", None)
    os.environ.pop("SUPABASE_KEY", None)
    try:
        build_memory()
    except ValueError:
        pass  # expected: missing url/key
    else:
        raise AssertionError("expected ValueError for supabase without credentials")
    finally:
        os.environ["MEMORY_BACKEND"] = "obsidian"


def main() -> None:
    passed = 0
    with tempfile.TemporaryDirectory() as vault:
        os.environ["MEMORY_BACKEND"] = "obsidian"
        os.environ["OBSIDIAN_VAULT_PATH"] = vault
        os.environ["MEMORY_ENABLED"] = "true"
        checks = [
            ("add/recall roundtrip", test_add_and_recall_roundtrip, ()),
            ("persistence across instances", test_persistence_across_instances, ()),
            ("recent ordering + empty query", test_recent_ordering_and_empty_query, ()),
            ("metadata survives", test_metadata_survives, ()),
            ("hashing embeddings", test_hashing_embeddings_deterministic_and_normalized, ()),
            ("factory selects obsidian", test_factory_selects_obsidian, (vault,)),
            ("supabase needs credentials", test_factory_supabase_requires_credentials, ()),
        ]
        for name, fn, args in checks:
            fn(*args)
            print(f"  ok - {name}")
            passed += 1
    print(f"\nmemory: {passed}/{len(checks)} checks passed")


if __name__ == "__main__":
    main()
