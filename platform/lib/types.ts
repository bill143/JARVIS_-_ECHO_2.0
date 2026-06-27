// Shared serialisable shapes passed from Server Components / API routes to
// Client Components. We keep these flat and JSON-safe (no Date objects).

export type PlanDTO = {
  id: string;
  challenge: string;
  minAccount: number;
  maxAccount: number;
  profitSplit: number | null;
};

export type CouponDTO = {
  id: string;
  code: string;
  percent: number | null;
  note: string | null;
  expiresAt: string | null;
};

export type TagDTO = {
  id: string;
  slug: string;
  label: string;
};

export type FirmDTO = {
  id: string;
  slug: string;
  name: string;
  logoUrl: string | null;
  rank: number | null;
  rating: number | null;
  legalEntity: string | null;
  hq: string | null;
  ceo: string | null;
  incorporated: string | null;
  summary: string | null;
  reviewBody: string | null;
  platforms: string[];
  liquidity: string | null;
  websiteUrl: string | null;
  affiliateUrl: string | null;
  plans: PlanDTO[];
  coupons: CouponDTO[];
  tags: TagDTO[];
  /** Best (largest) discount percent across coupons, or null. */
  topDiscount: number | null;
  /** Min/max account size derived from plans. */
  minAccount: number | null;
  maxAccount: number | null;
};

// A coupon enriched with its firm context for the offers page.
export type OfferDTO = CouponDTO & {
  firmSlug: string;
  firmName: string;
  affiliateUrl: string | null;
};
