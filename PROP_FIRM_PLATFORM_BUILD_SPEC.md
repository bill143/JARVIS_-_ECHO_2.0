# Prop Firm Review Platform — Build Specification (MVP Handoff)

> **Audience:** the build agent. This is the contract for the first deliverable. Build exactly what's in scope; defer everything marked OUT OF SCOPE. When a detail isn't specified, match the conventions already established in this document and keep it simple.

---

## 1. Objective

Build a **working Full MVP (frontend + backend)** of a proprietary-trading-firm review & comparison website — the public-facing product plus a real database and server layer behind it. It must run locally with a single command and be seeded with real sample data.

This is **Phase 2 of the master plan** (see `PROP_FIRM_PLATFORM_REQUIREMENTS.html` → Build Workflow tab) brought to life as runnable software.

## 2. Locked Decisions

| Decision | Locked value |
|---|---|
| First deliverable | Full MVP — frontend **and** backend |
| Frontend | **Next.js (App Router) + React + TypeScript + Tailwind CSS** |
| Backend | Next.js server (Route Handlers / Server Actions) |
| ORM / DB | **Prisma**, default datasource **SQLite** for local dev (schema written so it can switch to PostgreSQL for prod via the `provider`) |
| Theme | **Dark + Light with a user toggle** (dark is default) |
| Visual language | The "trading-tape" aesthetic from the requirements doc (mono accents, card layout) adapted to both themes |

## 3. MVP Scope

### IN SCOPE (build these)
- **Firm directory / "Best 10"** — ranked list + sortable/filterable comparison table.
- **Firm review page** — full profile per firm, driven by the database.
- **Comparison page** — dynamic "Firm A vs Firm B" side-by-side.
- **Search & filter** — by firm name, challenge type, platform, account size, discount.
- **Offers page** — list of active discounts/coupons across firms.
- **Static/legal pages** — About, Contact (static form, no send needed), Privacy, Terms, How We Test.
- **Backend** — Prisma schema + migrations + REST route handlers serving firms/plans/coupons/comparisons + seed script.
- **Design system** — design tokens for both themes, shared UI components, working theme toggle persisted to `localStorage`.
- **SEO basics** — per-page `<title>`/meta, semantic HTML, `sitemap.xml`, `robots.txt`, JSON-LD `AggregateRating`/`Review` on firm pages.

### OUT OF SCOPE (defer — do NOT build yet)
Firm portal, penny-auction, live spreads tracker, news blog, education hub, forum, awards, newsletter sending, payments/Stripe, user accounts/auth, banner ad serving, futures & sister verticals. Leave clean extension points but build none of these now.

## 4. Project Structure

Create the app in a top-level subfolder **`platform/`** (keep it isolated from the existing Python assistant in this repo).

```
platform/
  app/                      # Next.js App Router
    layout.tsx              # root layout, theme provider, header/footer
    page.tsx                # home = Best-10 directory
    firms/[slug]/page.tsx   # firm review
    compare/page.tsx        # comparison (reads ?a=&b=)
    offers/page.tsx
    about/ contact/ privacy/ terms/ how-we-test/   # static pages
    api/
      firms/route.ts
      firms/[slug]/route.ts
      compare/route.ts
      offers/route.ts
    sitemap.ts  robots.ts
  components/                # Header, Footer, ThemeToggle, FirmCard, FirmTable,
                            # RatingStars, DiscountBadge, CompareTable, Filters, etc.
  lib/                      # db (prisma client), seo helpers, types
  prisma/
    schema.prisma
    seed.ts                 # seeds the 10 firms below
  styles/                   # tailwind globals + CSS variables for both themes
  public/
  tailwind.config.ts  tsconfig.json  package.json  .env.example  README.md
```

## 5. Design System

### 5.1 Tokens (CSS variables, themed)

Reuse the requirements-doc palette for **dark**, and provide a clean **light** counterpart. Drive everything off CSS variables set on `:root` (light) and `[data-theme="dark"]` (dark) — Tailwind reads them via `theme.extend.colors`.

```css
/* Dark (default) */
[data-theme="dark"] {
  --bg:#0d1117; --panel:#11161f; --panel-edge:#1f2630; --line:#232b36;
  --text:#f5f3ee; --muted:#8a93a0;
  --accent:#2dd4a7;        /* primary / CTA */
  --amber:#e8b04b; --flag:#e5564b;
}
/* Light */
:root {
  --bg:#f5f3ee; --panel:#ffffff; --panel-edge:#e3e0d8; --line:#e3e0d8;
  --text:#0d1117; --muted:#5b6470;
  --accent:#0f9e7a; --amber:#b9821f; --flag:#c5392f;
}
```

- **Fonts:** system sans for body; a monospace stack for labels/numbers/eyebrows (matches the doc).
- **Components are theme-agnostic** — never hardcode hex in components; use the token classes only.

### 5.2 Theme toggle
- Header control switching `data-theme` on `<html>`, persisted to `localStorage`, respecting `prefers-color-scheme` on first visit. No flash of wrong theme (set theme before paint).

### 5.3 Core components to build
`Header` (nav + ThemeToggle), `Footer`, `FirmCard`, `FirmTable` (sortable), `Filters`, `RatingStars`, `DiscountBadge`, `CompareTable`, `Tape` (the stat ribbon), `Section`, `Button`, `Tag`.

## 6. Data Model (Prisma — MVP subset)

```prisma
model Firm {
  id            String   @id @default(cuid())
  slug          String   @unique
  name          String
  logoUrl       String?
  rank          Int?
  rating        Float?           // 0..5
  legalEntity   String?
  hq            String?
  ceo           String?
  incorporated  String?
  summary       String?          // short reputation blurb
  reviewBody    String?          // long-form review (markdown)
  platforms     String           // comma-separated e.g. "MT5,cTrader"
  liquidity     String?
  websiteUrl    String?
  affiliateUrl  String?
  plans         Plan[]
  coupons       Coupon[]
  tags          Tag[]    @relation("FirmTags")
  createdAt     DateTime @default(now())
}

model Plan {
  id          String @id @default(cuid())
  firm        Firm   @relation(fields: [firmId], references: [id])
  firmId      String
  challenge   String // "One-step" | "Two-step" | "Three-step" | "Instant" | "Futures"
  minAccount  Int
  maxAccount  Int
  profitSplit Int?   // percent
}

model Coupon {
  id        String   @id @default(cuid())
  firm      Firm     @relation(fields: [firmId], references: [id])
  firmId    String
  code      String
  percent   Int?     // discount %
  note      String?  // e.g. "120% refund"
  expiresAt DateTime?
}

model Tag {
  id    String @id @default(cuid())
  slug  String @unique
  label String
  firms Firm[] @relation("FirmTags")
}
```
> Switch `datasource db { provider = "sqlite" }` for dev; document the one-line change to `"postgresql"` for prod in the README.

## 7. Pages — what each must contain

- **Home `/`** — `Tape` ribbon (e.g. firms reviewed, avg rating, best discount); ranked `FirmTable` with columns: rank, firm (logo+name), rating, top discount, platforms, "Visit"/"Review" CTAs; `Filters` (challenge type, platform, account-size range, min discount) filtering the table client-side; sort by rank/rating/discount.
- **Firm review `/firms/[slug]`** — header (name, logo, rating, rank, `DiscountBadge`); profile facts (legal entity, HQ, CEO, incorporated, platforms, liquidity, account-size range from plans); plans table; long-form review; "Visit firm" (affiliate) + "Compare" CTAs; JSON-LD.
- **Compare `/compare?a=slug&b=slug`** — two-column `CompareTable` across every comparable field; firm pickers to change A/B.
- **Offers `/offers`** — cards of all coupons (firm, %, code with copy-to-clipboard, note, expiry, claim link); filter by firm/discount size.
- **Static pages** — readable content; "How We Test" states methodology; Contact is a non-functional styled form. Include a visible **affiliate-disclosure** line in the footer (FTC).

## 8. Seed Data (use these 10 real firms)

| Rank | Firm | slug | Discount | Code | Notes |
|---|---|---|---|---|---|
| 1 | FundingPips | fundingpips | 20% | FOREXPROPREVIEWS | ANKH PROP – FZCO, Dubai, inc. Aug 2022, CEO Khaled Ayesh, $5k–$200k, MT5/Match-Trader/cTrader |
| 2 | FundedNext | fundednext | 120% refund | FOREXPROPREVIEWS | |
| 3 | The5%ers | the5ers | 10% | FOREXPROPREVIEWS | |
| 4 | FTMO | ftmo | — | — | |
| 5 | Hola Prime | hola-prime | 15% | FOREXPROPREVIEWS | |
| 6 | E8 Markets | e8-markets | 5% | FOREXPROPREVIEWS | |
| 7 | FXIFY | fxify | 15% | FOREXPROPREVIEWS | |
| 8 | Blue Guardian | blue-guardian | 35% | FOREXPROPREVIEWS | |
| 9 | FunderPro | funderpro | 10% | FOREXPROPREVIEWS | |
| 10 | Fintokei | fintokei | 30% | FOREXPROPREVIEWS | |

For fields not given above, generate sensible, clearly-plausible placeholder values (account sizes, profit splits 80–90%, platforms, a 2–3 sentence summary, ratings 4.0–4.9) and add a code comment that they are placeholders to be replaced with verified data. Give each firm 1–2 plans and its coupon. Tag firms by challenge type.

## 9. Acceptance Criteria (Definition of Done)

1. `cd platform && npm install && npx prisma migrate dev && npm run seed && npm run dev` produces a running site at `localhost:3000` with all 10 firms.
2. All in-scope pages render in **both** themes; the toggle persists across reloads with no flash.
3. Directory filtering and sorting work; comparison page renders any two firms.
4. API route handlers return JSON for firms/firm-by-slug/compare/offers.
5. Fully responsive (mobile-first); no console errors; TypeScript compiles with no errors; `npm run lint` clean.
6. Firm pages include valid JSON-LD; `sitemap.xml` and `robots.txt` resolve.
7. `platform/README.md` documents setup, the SQLite→Postgres switch, scripts, and what's intentionally out of scope.

## 10. Conventions
- TypeScript strict; small, composable components; no unused deps.
- Accessible: semantic landmarks, labelled controls, visible focus, AA contrast in both themes.
- Keep it idiomatic Next.js App Router; prefer Server Components for data, Client Components only where interactivity needs it (filters, theme toggle, copy buttons).
- Do not invent features outside Section 3. Leave TODO comments where deferred features would later hook in.
