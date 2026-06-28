import type { FirmDTO, OfferDTO } from "@/lib/types";
import { FIRMS_DATA } from "@/lib/firms-data";

// The deployed site is read-only and serves the verified dataset from a static,
// committed snapshot (lib/firms-data.ts) — no database is required at build or
// runtime. The functions stay async so callers (and a future DB-backed portal)
// don't need to change. Regenerate the snapshot with: npm run snapshot.

export async function getFirms(): Promise<FirmDTO[]> {
  return FIRMS_DATA;
}

export async function getFirmBySlug(slug: string): Promise<FirmDTO | null> {
  return FIRMS_DATA.find((f) => f.slug === slug) ?? null;
}

export async function getOffers(): Promise<OfferDTO[]> {
  return FIRMS_DATA.flatMap((firm) =>
    firm.coupons.map((c) => ({
      ...c,
      firmSlug: firm.slug,
      firmName: firm.name,
      affiliateUrl: firm.affiliateUrl,
    })),
  ).sort((a, b) => (b.percent ?? -1) - (a.percent ?? -1));
}
