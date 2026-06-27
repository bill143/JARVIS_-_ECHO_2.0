# Prop Firm Review Platform — MVP

A working **Full MVP** (frontend **and** backend) of a forex proprietary-trading-firm
review & comparison website. Built with **Next.js (App Router) + React + TypeScript +
Tailwind CSS**, backed by **Prisma** (SQLite for local dev, swappable to PostgreSQL for prod).

## Quick start

```bash
cd platform
cp .env.example .env          # local SQLite config (a .env is already provided)
npm install                   # installs deps + runs `prisma generate`
npx prisma migrate dev        # creates dev.db and applies the schema
npm run seed                  # seeds the 10 firms from the spec
npm run dev                   # http://localhost:3000
```

Open http://localhost:3000 — you should see all 10 firms in the ranked directory.

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Start the dev server at `localhost:3000` |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (`next lint`) |
| `npm run typecheck` | `tsc --noEmit` (strict) |
| `npm run seed` | Seed the database (10 firms, plans, coupons, tags) |
| `npm run db:migrate` | `prisma migrate dev` |

## Architecture

```
platform/
  app/                       # App Router pages + API route handlers
    page.tsx                 # Home = Best-10 directory (Server Component)
    firms/[slug]/page.tsx    # Firm review (JSON-LD AggregateRating/Review)
    compare/page.tsx         # Compare (?a=&b=)
    offers/page.tsx          # Coupons / discounts
    about|contact|privacy|terms|how-we-test/   # static/legal pages
    api/firms | api/firms/[slug] | api/compare | api/offers   # REST handlers
    sitemap.ts  robots.ts
  components/                # Header, Footer, ThemeToggle, FirmCard, FirmTable,
                             # Filters, RatingStars, DiscountBadge, CompareTable,
                             # Tape, ui (Button/Tag/Section), OffersClient, …
  lib/                       # db (Prisma client), firms (data access + DTOs),
                             # seo helpers, types, format helpers
  prisma/                    # schema.prisma + seed.ts
  styles/globals.css         # Tailwind + CSS-variable theme tokens
```

- **Server Components** fetch data (home, firm, compare, offers). **Client
  Components** handle interactivity only (theme toggle, filters/sort, the
  comparison pickers, copy-to-clipboard).
- All data is mapped to flat, JSON-safe DTOs in `lib/firms.ts` before crossing
  into client components.

## Theming

- Tokens are CSS variables in `styles/globals.css`: `:root` is **light**,
  `[data-theme="dark"]` is **dark** (the default).
- Tailwind reads them via `theme.extend.colors` (`bg`, `panel`, `text`,
  `accent`, …). **Components never hardcode hex** — only token classes.
- The toggle (`components/ThemeToggle.tsx`) flips `data-theme` on `<html>` and
  persists to `localStorage`. An inline script (`components/ThemeScript.tsx`)
  runs **before paint** to apply the stored/`prefers-color-scheme` theme, so
  there is **no flash of the wrong theme**.

## SEO

- Per-page `<title>`/meta and canonical via `lib/seo.ts`.
- Firm pages embed **JSON-LD** (`Product` + `AggregateRating` + `Review`).
- `app/sitemap.ts` → `/sitemap.xml`, `app/robots.ts` → `/robots.txt`.
- Set `NEXT_PUBLIC_SITE_URL` in `.env` to your production origin for correct
  canonical / sitemap URLs.

## Switching SQLite → PostgreSQL (production)

1. In **`prisma/schema.prisma`**, change the datasource provider:
   ```prisma
   datasource db {
     provider = "postgresql"   // was "sqlite"
     url      = env("DATABASE_URL")
   }
   ```
2. Set `DATABASE_URL` in your environment to a Postgres connection string, e.g.
   ```
   DATABASE_URL="postgresql://user:password@host:5432/propfirm?schema=public"
   ```
3. Run migrations against Postgres:
   ```bash
   npx prisma migrate dev      # or `prisma migrate deploy` in CI/prod
   npm run seed
   ```
The Prisma models are written portably, so no schema changes are required
beyond the provider line.

## Seed data — important

The 10 firms (names, slugs, ranks, discounts, coupon code) come from the build
spec. **Only FundingPips** ships with spec-provided facts. Every other firm's
profile facts (legal entity, HQ, CEO, incorporation date, ratings, account
sizes, profit splits, summaries, review bodies) are **clearly-labelled
PLACEHOLDERS** in `prisma/seed.ts` — replace them with verified data before
launch (search the file for "placeholder").

## Troubleshooting

- **Prisma engine download fails / `npm install` errors in `@prisma/engines`
  postinstall** (only seen behind restrictive network proxies): install with
  `npm install --ignore-scripts`, then run `npx prisma generate` once normally
  to fetch the engine. In a standard environment `npm install` works as-is.

## Intentionally out of scope (deferred)

Per the spec, the following are **not** built in this MVP — clean extension
points / `TODO` comments are left where they'd later attach:

- Firm portal, penny-auction, live spreads tracker
- News blog, education hub, forum, awards
- Newsletter sending, payments/Stripe
- User accounts / authentication
- Banner-ad serving, futures & sister verticals
- A working contact-form backend (the form is a styled, non-sending demo)
```
