# JARVIS memory

Cross-session memory: JARVIS can `remember` facts and `recall` them in later
conversations. One interface (`MemoryStore`), two backends.

## Backends

| Backend | Recall | Deps | Status |
|---------|--------|------|--------|
| **Obsidian** (default) | keyword + recency over a local markdown vault | none (stdlib) | working, offline-tested |
| **Supabase** | cosine similarity over pgvector | `supabase`, embeddings | code-complete, runtime-blocked |

Choose with `MEMORY_BACKEND=obsidian|supabase` (see the root `.env.example`).

## Obsidian backend

Every memory is a markdown note in `OBSIDIAN_VAULT_PATH` (default `./memory_vault`,
git-ignored) with YAML frontmatter — open the folder in Obsidian to browse/edit.
No embeddings, no network. This is the default and is covered by `test_memory.py`.

## Supabase backend

1. `pip install -r memory/requirements-supabase.txt`
2. Run `memory/schema.sql` in your Supabase project (enables `vector`, creates
   the `memories` table + `match_memories` function). Keep the embedding
   dimension in the schema equal to `EMBEDDINGS_DIM`.
3. Set `MEMORY_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_KEY`, and an
   embeddings provider (`EMBEDDINGS_PROVIDER=openai` for real semantic recall —
   `EMBEDDINGS_BASE_URL` can point at ECHO).

> **RUNTIME-BLOCKED** until a Supabase project + keys are supplied. The code path
> is complete; it just hasn't been exercised against a live database.

## How JARVIS uses it

`memory_tools.register_memory_tools(llm)` registers the `remember`/`recall`
function tools when `MEMORY_ENABLED` is true, and is a no-op (logs a warning) if
the backend can't be built — so a memory misconfiguration never breaks the voice
loop.

## Tests

```bash
python test_memory.py   # offline: Obsidian roundtrip, persistence, embeddings, factory
```
