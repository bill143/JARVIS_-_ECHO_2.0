import { prisma } from "@/lib/db";
import type { FirmDTO, OfferDTO, PlanDTO, CouponDTO, TagDTO } from "@/lib/types";
import type { Prisma } from "@prisma/client";

const firmInclude = {
  plans: true,
  coupons: true,
  tags: true,
} satisfies Prisma.FirmInclude;

type FirmWithRelations = Prisma.FirmGetPayload<{ include: typeof firmInclude }>;

function toPlanDTO(p: FirmWithRelations["plans"][number]): PlanDTO {
  return {
    id: p.id,
    challenge: p.challenge,
    minAccount: p.minAccount,
    maxAccount: p.maxAccount,
    profitSplit: p.profitSplit,
  };
}

function toCouponDTO(c: FirmWithRelations["coupons"][number]): CouponDTO {
  return {
    id: c.id,
    code: c.code,
    percent: c.percent,
    note: c.note,
    expiresAt: c.expiresAt ? c.expiresAt.toISOString() : null,
  };
}

function toTagDTO(t: FirmWithRelations["tags"][number]): TagDTO {
  return { id: t.id, slug: t.slug, label: t.label };
}

export function toFirmDTO(firm: FirmWithRelations): FirmDTO {
  const platforms = firm.platforms
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const discounts = firm.coupons
    .map((c) => c.percent)
    .filter((p): p is number => typeof p === "number");
  const topDiscount = discounts.length ? Math.max(...discounts) : null;

  const minAccount = firm.plans.length
    ? Math.min(...firm.plans.map((p) => p.minAccount))
    : null;
  const maxAccount = firm.plans.length
    ? Math.max(...firm.plans.map((p) => p.maxAccount))
    : null;

  return {
    id: firm.id,
    slug: firm.slug,
    name: firm.name,
    logoUrl: firm.logoUrl,
    rank: firm.rank,
    rating: firm.rating,
    legalEntity: firm.legalEntity,
    hq: firm.hq,
    ceo: firm.ceo,
    incorporated: firm.incorporated,
    summary: firm.summary,
    reviewBody: firm.reviewBody,
    platforms,
    liquidity: firm.liquidity,
    websiteUrl: firm.websiteUrl,
    affiliateUrl: firm.affiliateUrl,
    plans: firm.plans.map(toPlanDTO),
    coupons: firm.coupons.map(toCouponDTO),
    tags: firm.tags.map(toTagDTO),
    topDiscount,
    minAccount,
    maxAccount,
  };
}

export async function getFirms(): Promise<FirmDTO[]> {
  const firms = await prisma.firm.findMany({
    include: firmInclude,
    orderBy: [{ rank: "asc" }, { name: "asc" }],
  });
  return firms.map(toFirmDTO);
}

export async function getFirmBySlug(slug: string): Promise<FirmDTO | null> {
  const firm = await prisma.firm.findUnique({
    where: { slug },
    include: firmInclude,
  });
  return firm ? toFirmDTO(firm) : null;
}

export async function getOffers(): Promise<OfferDTO[]> {
  const coupons = await prisma.coupon.findMany({
    include: { firm: true },
    orderBy: [{ percent: "desc" }],
  });
  return coupons.map((c) => ({
    id: c.id,
    code: c.code,
    percent: c.percent,
    note: c.note,
    expiresAt: c.expiresAt ? c.expiresAt.toISOString() : null,
    firmSlug: c.firm.slug,
    firmName: c.firm.name,
    affiliateUrl: c.firm.affiliateUrl,
  }));
}
