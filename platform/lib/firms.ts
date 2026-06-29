import type { FirmDTO, OfferDTO } from "@/lib/types";
import { FIRMS_DATA } from "@/lib/firms-data";
import { withComputedRatings } from "@/lib/rating";

// The deployed site is read-only and serves the verified dataset from a static,
// committed snapshot (lib/firms-data.ts) — no database is required at build or
// runtime. Each firm's rating is filled by a transparent algorithmic score
// (lib/rating.ts) where no editorial rating is stored. The functions stay async
// so callers (and a future DB-backed portal) don't need to change.

const FIRMS: FirmDTO[] = withComputedRatings(FIRMS_DATA);

export async function getFirms(): Promise<FirmDTO[]> {
  return FIRMS;
}

export async function getFirmBySlug(slug: string): Promise<FirmDTO | null> {
  return FIRMS.find((f) => f.slug === slug) ?? null;
}

export async function getOffers(): Promise<OfferDTO[]> {
  return FIRMS.flatMap((firm) =>
    firm.coupons.map((c) => ({
      ...c,
      firmSlug: firm.slug,
      firmName: firm.name,
      affiliateUrl: firm.affiliateUrl,
    })),
  ).sort((a, b) => (b.percent ?? -1) - (a.percent ?? -1));
}
