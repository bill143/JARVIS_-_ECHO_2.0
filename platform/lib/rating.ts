import type { FirmDTO } from "@/lib/types";

/**
 * Provisional, transparent algorithmic score (0–5) for each firm.
 *
 * Derived ONLY from verified hard attributes we hold for every firm — never
 * from user reviews (we have none yet) and never from invented per-criterion
 * opinions. It exists to replace "Unrated" with a defensible, reproducible
 * number until a real user-review system is live. Factors and weights are
 * intentionally simple and documented on /how-we-test; tune them, or replace
 * the whole thing with editorial/review-based scores, freely.
 */

export const RATING_WEIGHTS = {
  rewardSplit: 0.3, // highest reward (profit) split %
  scaling: 0.15, // funded-capital ceiling (log-scaled)
  platforms: 0.15, // number of supported platforms
  variety: 0.15, // number of challenge models
  value: 0.25, // current discount %
} as const;

type FactorKey = keyof typeof RATING_WEIGHTS;

// Scores cluster in a realistic band rather than spanning a harsh 0–5.
const MIN_SCORE = 3.2;
const MAX_SCORE = 4.9;

function maxSplit(f: FirmDTO): number {
  const splits = f.plans.map((p) => p.profitSplit ?? 0);
  return splits.length ? Math.max(...splits) : 0;
}

function rawFactors(f: FirmDTO): Record<FactorKey, number> {
  return {
    rewardSplit: maxSplit(f),
    scaling: f.maxAccount ? Math.log10(f.maxAccount) : 0,
    platforms: f.platforms.length,
    variety: f.tags.length,
    value: f.topDiscount ?? 0,
  };
}

function normalizer(values: number[]): (v: number) => number {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  return (v: number) => (span === 0 ? 0.5 : (v - min) / span);
}

/**
 * Returns a new array where each firm's `rating` is filled with the computed
 * score when it is null. A stored editorial rating, if present, is preserved.
 */
export function withComputedRatings(firms: FirmDTO[]): FirmDTO[] {
  const factors = firms.map(rawFactors);
  const keys = Object.keys(RATING_WEIGHTS) as FactorKey[];
  const norms = Object.fromEntries(
    keys.map((k) => [k, normalizer(factors.map((f) => f[k]))]),
  ) as Record<FactorKey, (v: number) => number>;

  return firms.map((firm, i) => {
    if (firm.rating != null) return firm;
    const f = factors[i];
    const score01 = keys.reduce(
      (sum, k) => sum + RATING_WEIGHTS[k] * norms[k](f[k]),
      0,
    );
    const rating =
      Math.round((MIN_SCORE + score01 * (MAX_SCORE - MIN_SCORE)) * 10) / 10;
    return { ...firm, rating };
  });
}
