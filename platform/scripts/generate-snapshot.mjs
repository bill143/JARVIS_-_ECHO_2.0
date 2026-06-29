/**
 * Regenerate lib/firms-data.ts — the static, committed snapshot of the verified
 * firm dataset that powers the deployed (read-only) site, so no database is
 * needed at build or runtime.
 *
 * Flow: edit prisma/seed.ts -> `npm run seed` (writes the local SQLite DB) ->
 * `npm run snapshot` (this script, reads the DB and rewrites the snapshot).
 *
 * Usage: npm run snapshot
 */
import { PrismaClient } from "@prisma/client";
import { writeFileSync } from "node:fs";

const prisma = new PrismaClient();

const firms = await prisma.firm.findMany({
  include: { plans: true, coupons: true, tags: true },
  orderBy: [{ rank: "asc" }, { name: "asc" }],
});

const dto = firms.map((firm) => {
  const platforms = firm.platforms.split(",").map((s) => s.trim()).filter(Boolean);
  const discounts = firm.coupons.map((c) => c.percent).filter((x) => typeof x === "number");
  const topDiscount = discounts.length ? Math.max(...discounts) : null;
  const minAccount = firm.plans.length ? Math.min(...firm.plans.map((p) => p.minAccount)) : null;
  const maxAccount = firm.plans.length ? Math.max(...firm.plans.map((p) => p.maxAccount)) : null;
  return {
    id: firm.id, slug: firm.slug, name: firm.name, logoUrl: firm.logoUrl,
    rank: firm.rank, rating: firm.rating, legalEntity: firm.legalEntity,
    hq: firm.hq, ceo: firm.ceo, incorporated: firm.incorporated,
    summary: firm.summary, reviewBody: firm.reviewBody, platforms,
    liquidity: firm.liquidity, websiteUrl: firm.websiteUrl, affiliateUrl: firm.affiliateUrl,
    plans: firm.plans.map((x) => ({ id: x.id, challenge: x.challenge, minAccount: x.minAccount, maxAccount: x.maxAccount, profitSplit: x.profitSplit })),
    coupons: firm.coupons.map((c) => ({ id: c.id, code: c.code, percent: c.percent, note: c.note, expiresAt: c.expiresAt ? c.expiresAt.toISOString() : null })),
    tags: firm.tags.map((t) => ({ id: t.id, slug: t.slug, label: t.label })),
    topDiscount, minAccount, maxAccount,
  };
});

const header =
  "// AUTO-GENERATED static data snapshot of the verified firm dataset.\n" +
  "// Source of truth for the deployed (read-only) site — no database needed at\n" +
  "// runtime. Regenerate via: npm run snapshot (see scripts/generate-snapshot.mjs).\n" +
  "// Do not hand-edit.\n\n" +
  'import type { FirmDTO } from "@/lib/types";\n\n' +
  "export const FIRMS_DATA: FirmDTO[] = ";

writeFileSync("lib/firms-data.ts", header + JSON.stringify(dto, null, 2) + ";\n");
console.log(`Wrote lib/firms-data.ts with ${dto.length} firms`);

await prisma.$disconnect();
