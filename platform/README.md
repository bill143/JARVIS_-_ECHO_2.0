# Prop Firm Review Platform

An affiliate-style **review & comparison website for forex proprietary-trading ("prop") firms** — ranked directory, individual firm reviews, head-to-head comparisons, and a discounts/offers hub.

Built with **Next.js (App Router) · React · TypeScript · Tailwind CSS**. The live site is **read-only and fully self-contained**: it serves a committed data snapshot, so **no database is needed to build or run it**. Prisma + SQLite are used only locally to edit and regenerate that snapshot.

> This repo (`tradebridge`) hosts the platform. Planning artifacts live in [`/docs`](./docs).

## Quick start

```bash
npm install        # installs deps (runs `prisma generate`)
npm run dev        # http://localhost:3000
```

That's it — the app boots against the committed snapshot (`lib/firms-data.ts`). No migrate/seed step required just to run it.

Open http://localhost:3000 and you'll see all 10 firms in the ranked directory, in dark or light theme.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server at `localhost:3000` |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (`next lint`) |
| `npm run typecheck` | `tsc --noEmit` (strict) |
| `npm run seed` | Write the 10 firms into the local SQLite DB (for editing data) |
| `npm run snapshot` | Regenerate `lib/firms-data.ts` from the local DB |
| `npm run db:migrate` | `prisma migrate dev` (local schema work) |

## Architecture

```
.                            # app at repo root (deploy-ready)
  app/                       # App Router pages + API route handlers
    page.tsx                 # Home = ranked "Best 10" directory
    firms/[slug]/page.tsx    # Firm review (JSON-LD Product/AggregateRating/Review)
    compare/page.tsx         # Compare two firms (?a=&b=)
    offers/page.tsx          # Coupons / discounts hub
    about|contact|privacy|terms|how-we-test/   # static / legal pages
    api/firms | api/firms/[slug] | api/compare | api/offers   # REST handlers
    sitemap.ts  robots.ts
  components/                # Header, Footer, ThemeToggle, FirmTable, FirmCard,
                             # Filters, RatingStars, DiscountBadge, CompareTable, …
  lib/
    firms-data.ts            # ← committed static snapshot (source of truth at runtime)
    firms.ts                 # data accessors (getFirms/getFirmBySlug/getOffers)
    types.ts  seo.ts  format.ts
  prisma/                    # schema.prisma + seed.ts  (LOCAL data editing only)
  scripts/generate-snapshot.mjs   # rebuilds lib/firms-data.ts from the DB
  styles/globals.css         # Tailwind + CSS-variable theme tokens
  docs/                      # requirements + build spec
```

- **Server Components** read data; **Client Components** handle interactivity only (theme toggle, filters/sort, comparison pickers, copy-to-clipboard).
- The runtime never touches a database — `lib/firms.ts` serves the static snapshot. Prisma stays available for local data work and as a clean extension point for a future DB-backed portal.

## Updating the firm data

The data flow is **edit → seed → snapshot → commit**:

```bash
# 1. edit the dataset
$EDITOR prisma/seed.ts

# 2. write it into the local SQLite DB
npm run seed

# 3. regenerate the committed snapshot the site serves
npm run snapshot

# 4. commit lib/firms-data.ts
git add prisma/seed.ts lib/firms-data.ts && git commit -m "Update firm data"
```

### Data provenance (important)

Firm **identity facts** (legal entity, HQ, CEO, founded year) were verified **June 2026 under a strict primary-source rule** — kept only if confirmed on the firm's official domain, official LinkedIn, or a government registry. Anything not primary-confirmable is **`null`** (rendered as "—"), never a guessed value; each firm's `// VERIFY` note in `prisma/seed.ts` records the source + reason. Product fields (platforms, account sizes, splits, challenge types) may rest on secondary corroboration where official sites block automated access (noted inline). **Editorial ratings are `null`** pending defined ranking criteria.

## Theming

- Tokens are CSS variables in `styles/globals.css`: `:root` = **light**, `[data-theme="dark"]` = **dark** (default). Tailwind reads them via `theme.extend.colors`; components never hardcode hex.
- The toggle flips `data-theme` on `<html>` and persists to `localStorage`. An inline script applies the stored / `prefers-color-scheme` theme **before paint** — no flash of the wrong theme.

## SEO

- Per-page `<title>`/meta + canonical via `lib/seo.ts`.
- Firm pages embed **JSON-LD** (`Product` + `AggregateRating` + `Review`).
- `/sitemap.xml` and `/robots.txt` are generated.
- Set `NEXT_PUBLIC_SITE_URL` to your production origin for correct canonical/sitemap URLs.

## Deployment

Because the site is self-contained (no DB, no secrets) and the app is at the **repo root**, deploying is trivial:

- **Vercel:** import the repo → framework auto-detects **Next.js** → no Root Directory override, **no environment variables required** → deploy. (Optionally set `NEXT_PUBLIC_SITE_URL`.)
- Any Node host works the same way (`npm install && npm run build && npm run start`).

## Optional: PostgreSQL (for a future DB-backed portal)

The public site needs no database, but if you later add write features (e.g. a firm portal), Prisma is ready:

1. In `prisma/schema.prisma` set `provider = "postgresql"` and `url = env("DATABASE_URL")`.
2. Provide `DATABASE_URL`, then `npx prisma migrate deploy && npm run seed`.

The models are written portably — only the provider line changes.

## Troubleshooting

- **`npm install` fails in `@prisma/engines` postinstall** (only behind restrictive network proxies): `npm install --ignore-scripts`, then `npx prisma generate` once. Standard environments work as-is.

## Intentionally out of scope (deferred)

Clean extension points / `TODO`s are left where these would attach:

- Firm portal · penny-auction · live spreads tracker
- News blog · education hub · forum · awards
- Newsletter sending · payments/Stripe · user accounts/auth
- Banner-ad serving · futures & sister verticals
- A real contact-form backend (the form is a styled, non-sending demo)

See [`docs/PROP_FIRM_PLATFORM_REQUIREMENTS.html`](./docs) for the full 23-item scope, build workflow, and technical spec.
