# ECHO — multi-provider LLM proxy

ECHO is the router/brain: one OpenAI-compatible endpoint in front of Anthropic,
OpenAI, Google, DeepSeek, and xAI, with **6 semantic tiers**, **16 model
aliases**, automatic **fallback chains**, per-request **cost/token/latency
logging**, and **Langfuse** observability. Built on [LiteLLM](https://github.com/BerriAI/litellm)
(MIT).

JARVIS (and any other client) talks only to ECHO — never to a provider directly.

## Tiers

| Tier | Purpose | Primary model |
|------|---------|---------------|
| `tier-compliance` | high-accuracy, low-risk | Anthropic Sonnet |
| `tier-long-doc`   | large-context docs | Gemini 1.5 Pro |
| `tier-strategy`   | planning / synthesis | Anthropic Sonnet |
| `tier-bulk`       | cheap/fast volume | GPT-4o-mini |
| `tier-reasoning`  | step-by-step reasoning | DeepSeek Reasoner |
| `tier-realtime`   | lowest latency (voice) | Anthropic Haiku |

Each tier (and each of the 16 aliases) has a cross-provider fallback chain — see
`config.yaml`. Edit model ids there as providers release new versions; the alias
names are the stable contract.

## Run

```bash
cd echo
cp .env.example .env          # add provider keys + a strong ECHO_MASTER_KEY
docker compose up --build     # echo :4000, Langfuse :3000, Postgres
```

Three containers come up: **echo** (the proxy), **langfuse** (dashboards), and
**postgres** (Langfuse's store). All report healthy via their healthchecks.

## Call it (OpenAI-compatible)

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $ECHO_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "tier-realtime", "messages": [{"role":"user","content":"hi"}]}'
```

## Endpoints

- `POST /v1/chat/completions` — OpenAI-compatible chat (request a tier or alias).
- `GET  /v1/models` — list configured aliases + tiers.
- `GET  /health` — per-model health (validates provider keys with a live ping).
- `GET  /health/liveliness` — fast liveness probe (used by Docker).

## Health / preflight

```bash
python healthcheck.py          # which provider keys are present
python healthcheck.py --live   # prove each key works (Block-8 preflight)
python validate_config.py      # static: 6 tiers, 16 aliases, fallbacks (no network)
```

## Notes / status

- **CODE-COMPLETE.** The full live path (real provider calls, Block-8) is
  **RUNTIME-BLOCKED** until provider keys are supplied — see `.env.example`.
- Secrets live only in `echo/.env` (git-ignored). Never commit real keys.
- Deploy to Railway is **human-gated**: this repo is deployable (Dockerfile +
  config), but nothing is auto-pushed to prod.
