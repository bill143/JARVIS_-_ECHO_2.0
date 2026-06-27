/**
 * Seed script for the Prop Firm Review Platform.
 *
 * Seeds the 10 real firms from Section 8 of the build spec. Only FundingPips
 * ships with spec-provided facts; every other firm's profile facts (legal
 * entity, HQ, CEO, incorporation, ratings, account sizes, profit splits,
 * summaries, review bodies) are PLACEHOLDERS that are clearly plausible but
 * MUST be replaced with verified data before launch. They are marked below.
 *
 * Run with: npm run seed
 */
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

// Challenge-type tags. Firms reference these by slug.
const TAGS: { slug: string; label: string }[] = [
  { slug: "one-step", label: "One-step" },
  { slug: "two-step", label: "Two-step" },
  { slug: "three-step", label: "Three-step" },
  { slug: "instant", label: "Instant" },
];

type SeedPlan = {
  challenge: string;
  minAccount: number;
  maxAccount: number;
  profitSplit?: number;
};

type SeedCoupon = {
  code: string;
  percent?: number;
  note?: string;
  expiresAt?: Date;
};

type SeedFirm = {
  slug: string;
  name: string;
  rank: number;
  rating: number;
  legalEntity?: string;
  hq?: string;
  ceo?: string;
  incorporated?: string;
  summary: string;
  reviewBody: string;
  platforms: string;
  liquidity?: string;
  websiteUrl: string;
  affiliateUrl: string;
  tagSlugs: string[];
  plans: SeedPlan[];
  coupon?: SeedCoupon;
};

const COUPON_CODE = "FOREXPROPREVIEWS";

// NOTE: Apart from FundingPips (which uses spec-provided facts), all profile
// facts below are PLACEHOLDERS — replace with verified data before launch.
const FIRMS: SeedFirm[] = [
  {
    slug: "fundingpips",
    name: "FundingPips",
    rank: 1,
    rating: 4.8,
    // Spec-provided facts (FundingPips):
    legalEntity: "ANKH PROP – FZCO",
    hq: "Dubai, UAE",
    ceo: "Khaled Ayesh",
    incorporated: "August 2022",
    summary:
      "FundingPips has rapidly become one of the most talked-about forex prop firms, known for fast scaling and a trader-friendly evaluation. Strong community reputation and competitive pricing.",
    reviewBody:
      "## Overview\n\nFundingPips offers one- and two-step evaluations across MT5, Match-Trader and cTrader. The firm is operated by ANKH PROP – FZCO out of Dubai and has built a strong reputation for fast payouts and responsive support.\n\n## Evaluation\n\nAccount sizes range from $5k to $200k with profit splits up to 90%. The two-step path is the most popular for its balanced targets.\n\n> Placeholder review copy beyond spec-provided facts — replace with a verified, hands-on review before launch.",
    platforms: "MT5,Match-Trader,cTrader",
    liquidity: "Tier-1 aggregated liquidity (placeholder)",
    websiteUrl: "https://fundingpips.com",
    affiliateUrl: "https://fundingpips.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 20, note: "20% off all challenges" },
  },
  {
    // PLACEHOLDER facts below — verify before launch.
    slug: "fundednext",
    name: "FundedNext",
    rank: 2,
    rating: 4.7,
    legalEntity: "FundedNext Ltd (placeholder)",
    hq: "Dubai, UAE (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2022 (placeholder)",
    summary:
      "FundedNext is a large, well-known prop firm offering multiple evaluation models including an upfront refund on the challenge fee. Popular for its generous scaling plan.",
    reviewBody:
      "## Overview\n\nFundedNext runs several evaluation models and is known for its 15% profit share during the challenge phase on some models, plus a refundable fee.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT4,MT5",
    liquidity: "Aggregated liquidity (placeholder)",
    websiteUrl: "https://fundednext.com",
    affiliateUrl: "https://fundednext.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "Two-step", minAccount: 6000, maxAccount: 200000, profitSplit: 90 },
      { challenge: "One-step", minAccount: 6000, maxAccount: 100000, profitSplit: 85 },
    ],
    coupon: { code: COUPON_CODE, note: "120% refund on first payout" },
  },
  {
    slug: "the5ers",
    name: "The5%ers",
    rank: 3,
    rating: 4.6,
    legalEntity: "The 5%ers (placeholder)",
    hq: "Israel (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2016 (placeholder)",
    summary:
      "The5%ers is one of the longest-running prop firms, offering instant-funding and high-stakes challenge programs with an emphasis on low-risk, consistent trading.",
    reviewBody:
      "## Overview\n\nThe5%ers offers both instant funding and challenge accounts, with a focus on steady growth and a transparent scaling plan.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT5",
    liquidity: "Aggregated liquidity (placeholder)",
    websiteUrl: "https://the5ers.com",
    affiliateUrl: "https://the5ers.com/?ref=forexpropreviews",
    tagSlugs: ["two-step", "instant"],
    plans: [
      { challenge: "Instant", minAccount: 4000, maxAccount: 100000, profitSplit: 80 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 100000, profitSplit: 85 },
    ],
    coupon: { code: COUPON_CODE, percent: 10, note: "10% off challenges" },
  },
  {
    slug: "ftmo",
    name: "FTMO",
    rank: 4,
    rating: 4.7,
    legalEntity: "FTMO s.r.o. (placeholder)",
    hq: "Prague, Czech Republic (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2015 (placeholder)",
    summary:
      "FTMO is the industry benchmark prop firm — a two-step evaluation, robust risk rules and a reputation for reliable payouts built over many years.",
    reviewBody:
      "## Overview\n\nFTMO popularised the two-step evaluation model and remains the most recognised name in the space. Known for strong infrastructure and consistent payouts.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT4,MT5,cTrader",
    liquidity: "Tier-1 liquidity (placeholder)",
    websiteUrl: "https://ftmo.com",
    affiliateUrl: "https://ftmo.com/?ref=forexpropreviews",
    tagSlugs: ["two-step"],
    plans: [
      { challenge: "Two-step", minAccount: 10000, maxAccount: 200000, profitSplit: 90 },
    ],
    // No coupon (spec: "—").
  },
  {
    slug: "hola-prime",
    name: "Hola Prime",
    rank: 5,
    rating: 4.5,
    legalEntity: "Hola Prime (placeholder)",
    hq: "UAE (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2024 (placeholder)",
    summary:
      "Hola Prime is a newer firm that has gained traction with flexible evaluation options and fast payout claims. One of the rising names in the space.",
    reviewBody:
      "## Overview\n\nHola Prime offers one- and two-step evaluations with competitive targets and a focus on rapid payouts.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT5,cTrader",
    liquidity: "Aggregated liquidity (placeholder)",
    websiteUrl: "https://holaprime.com",
    affiliateUrl: "https://holaprime.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 15, note: "15% off challenges" },
  },
  {
    slug: "e8-markets",
    name: "E8 Markets",
    rank: 6,
    rating: 4.4,
    legalEntity: "E8 Funding LLC (placeholder)",
    hq: "Dallas, USA (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2021 (placeholder)",
    summary:
      "E8 Markets is known for its flexible, customisable evaluation and a strong trader dashboard. Popular among traders who want tailored challenge parameters.",
    reviewBody:
      "## Overview\n\nE8 Markets offers configurable one-, two- and three-step evaluations with a polished platform experience.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT5,Match-Trader",
    liquidity: "Aggregated liquidity (placeholder)",
    websiteUrl: "https://e8markets.com",
    affiliateUrl: "https://e8markets.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "three-step"],
    plans: [
      { challenge: "Two-step", minAccount: 5000, maxAccount: 250000, profitSplit: 80 },
      { challenge: "Three-step", minAccount: 5000, maxAccount: 250000, profitSplit: 80 },
    ],
    coupon: { code: COUPON_CODE, percent: 5, note: "5% off challenges" },
  },
  {
    slug: "fxify",
    name: "FXIFY",
    rank: 7,
    rating: 4.4,
    legalEntity: "FXIFY (placeholder)",
    hq: "London, UK (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2023 (placeholder)",
    summary:
      "FXIFY offers a wide range of evaluation models with highly customisable parameters and add-ons, backed by an established broker partner.",
    reviewBody:
      "## Overview\n\nFXIFY provides one-, two- and three-step challenges with optional add-ons and up to 90% profit splits.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT4,MT5",
    liquidity: "Broker-backed liquidity (placeholder)",
    websiteUrl: "https://fxify.com",
    affiliateUrl: "https://fxify.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "three-step"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 15, note: "15% off challenges" },
  },
  {
    slug: "blue-guardian",
    name: "Blue Guardian",
    rank: 8,
    rating: 4.3,
    legalEntity: "Blue Guardian (placeholder)",
    hq: "UAE (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2021 (placeholder)",
    summary:
      "Blue Guardian focuses on capital-preservation-friendly rules and a clean evaluation process, appealing to risk-conscious traders.",
    reviewBody:
      "## Overview\n\nBlue Guardian offers one- and two-step evaluations with an emphasis on consistency and capital preservation.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT5,cTrader",
    liquidity: "Aggregated liquidity (placeholder)",
    websiteUrl: "https://blueguardian.com",
    affiliateUrl: "https://blueguardian.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "Two-step", minAccount: 5000, maxAccount: 200000, profitSplit: 85 },
    ],
    coupon: { code: COUPON_CODE, percent: 35, note: "35% off challenges" },
  },
  {
    slug: "funderpro",
    name: "FunderPro",
    rank: 9,
    rating: 4.3,
    legalEntity: "FunderPro (placeholder)",
    hq: "London, UK (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2022 (placeholder)",
    summary:
      "FunderPro pairs its evaluation with its own proprietary platform and a regulated broker partner, positioning itself as a transparent option.",
    reviewBody:
      "## Overview\n\nFunderPro offers one- and two-step challenges on its proprietary TradeLocker-based platform.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "TradeLocker,MT5",
    liquidity: "Broker-backed liquidity (placeholder)",
    websiteUrl: "https://funderpro.com",
    affiliateUrl: "https://funderpro.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "Two-step", minAccount: 5000, maxAccount: 200000, profitSplit: 80 },
    ],
    coupon: { code: COUPON_CODE, percent: 10, note: "10% off challenges" },
  },
  {
    slug: "fintokei",
    name: "Fintokei",
    rank: 10,
    rating: 4.2,
    legalEntity: "Fintokei (placeholder)",
    hq: "Japan / EU (placeholder)",
    ceo: "Placeholder Name",
    incorporated: "2023 (placeholder)",
    summary:
      "Fintokei targets a global (notably Japanese) audience with multiple evaluation tiers and a polished, localised experience.",
    reviewBody:
      "## Overview\n\nFintokei offers several evaluation tiers with localisation for multiple regions and competitive scaling.\n\n> Placeholder review copy — replace with a verified, hands-on review before launch.",
    platforms: "MT5,DXtrade",
    liquidity: "Aggregated liquidity (placeholder)",
    websiteUrl: "https://fintokei.com",
    affiliateUrl: "https://fintokei.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "Two-step", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 30, note: "30% off challenges" },
  },
];

async function main() {
  console.log("Seeding database…");

  // Idempotent: clear existing rows so re-seeding is safe.
  await prisma.coupon.deleteMany();
  await prisma.plan.deleteMany();
  await prisma.firm.deleteMany();
  await prisma.tag.deleteMany();

  // Tags first.
  for (const tag of TAGS) {
    await prisma.tag.create({ data: tag });
  }

  for (const firm of FIRMS) {
    await prisma.firm.create({
      data: {
        slug: firm.slug,
        name: firm.name,
        rank: firm.rank,
        rating: firm.rating,
        legalEntity: firm.legalEntity,
        hq: firm.hq,
        ceo: firm.ceo,
        incorporated: firm.incorporated,
        summary: firm.summary,
        reviewBody: firm.reviewBody,
        platforms: firm.platforms,
        liquidity: firm.liquidity,
        websiteUrl: firm.websiteUrl,
        affiliateUrl: firm.affiliateUrl,
        tags: {
          connect: firm.tagSlugs.map((slug) => ({ slug })),
        },
        plans: {
          create: firm.plans,
        },
        coupons: firm.coupon ? { create: [firm.coupon] } : undefined,
      },
    });
  }

  const firmCount = await prisma.firm.count();
  console.log(`Seeded ${firmCount} firms.`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
