/**
 * Seed script for the Prop Firm Review Platform.
 *
 * Seeds the 10 firms with VERIFIED facts gathered Jun 2026 from each firm's
 * official site and reputable secondary sources (FXEmpire, BrokerAnalysis,
 * FX News Group, TradersUnion, etc.). Figures can change and some details
 * carry caveats — see the `// NOTE:` comments on individual firms. Always
 * confirm against the firm's own site before relying on a number for launch.
 *
 * Ratings are our own editorial scores (not scraped). Discount/coupon values
 * come from the forexpropreviews.com ranking. Liquidity-provider data was not
 * reliably verifiable and is intentionally omitted rather than guessed.
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

const VERIFIED = "_Facts verified Jun 2026 from public sources; figures may change — confirm on the firm's own site._";

const FIRMS: SeedFirm[] = [
  {
    slug: "fundingpips",
    name: "FundingPips",
    rank: 1,
    rating: 4.8,
    legalEntity: "ANKH PROP FZCO (UAE)",
    hq: "Dubai, United Arab Emirates",
    ceo: "Khaled Ayesh",
    incorporated: "2022",
    summary:
      "FundingPips is a Dubai-based forex/CFD proprietary trading firm founded in 2022 that offers one-step, two-step, and instant (Zero) evaluation models on MT5, cTrader, Match-Trader, and TradeLocker.",
    reviewBody:
      "## Overview\n\nFundingPips, operated by ANKH PROP FZCO out of Dubai, launched in 2022 and quickly became one of the most talked-about firms in the space. It runs one-step, two-step, and instant (Zero) evaluations across MT5, cTrader, Match-Trader, and TradeLocker.\n\n## Funding & splits\n\nFunded accounts run from $5,000 up to $100,000, with a scaling program that can grow capital toward roughly $2M. Profit splits reach up to 100% on certain payout structures (standard funded splits are commonly cited at 80–95%).\n\n" + VERIFIED,
    platforms: "MT5,cTrader,Match-Trader,TradeLocker",
    websiteUrl: "https://fundingpips.com",
    affiliateUrl: "https://fundingpips.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "instant"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 100000, profitSplit: 100 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 100000, profitSplit: 100 },
      { challenge: "Instant", minAccount: 5000, maxAccount: 100000, profitSplit: 100 },
    ],
    coupon: { code: COUPON_CODE, percent: 20, note: "20% off all challenges" },
  },
  {
    slug: "fundednext",
    name: "FundedNext",
    rank: 2,
    rating: 4.7,
    legalEntity: "GrowthNext F.Z.C. (UAE)",
    hq: "Ajman, United Arab Emirates",
    ceo: "Abdullah Jayed",
    incorporated: "2022",
    summary:
      "FundedNext is an Ajman (UAE)-based forex/CFD proprietary trading firm founded in 2022 that offers one-step, two-step, and instant funding models (Stellar series) on MT4, MT5, cTrader, and Match-Trader.",
    reviewBody:
      "## Overview\n\nFundedNext, operated by GrowthNext F.Z.C. in Ajman, UAE, has grown into one of the largest names in prop trading since its 2022 launch. Its Stellar series spans one-step, two-step, and instant funding on MT4, MT5, cTrader, and Match-Trader.\n\n## Funding & splits\n\nEntry starts as low as $2,000 (Stellar Instant) up to $200,000, with profit splits up to 95% on CFD models. The firm is known for a refundable challenge fee and generous scaling.\n\n" + VERIFIED,
    platforms: "MT4,MT5,cTrader,Match-Trader",
    websiteUrl: "https://fundednext.com",
    affiliateUrl: "https://fundednext.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "instant"],
    plans: [
      { challenge: "Instant", minAccount: 2000, maxAccount: 200000, profitSplit: 95 },
      { challenge: "Two-step", minAccount: 6000, maxAccount: 200000, profitSplit: 90 },
      { challenge: "One-step", minAccount: 6000, maxAccount: 100000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, note: "120% refund on first payout" },
  },
  {
    // NOTE: legalEntity and CEO are NULL. the5ers.com blocks automated access
    // (HTTP 503 on all paths, Jun 2026) and official LinkedIn is login-walled,
    // so neither "Five Percent Online Ltd." nor CEO "Gil Ben Hur" could be
    // confirmed from a primary source (both secondary-only). HQ "Ra'anana,
    // Israel" and year 2016 are likewise secondary. accountMax $4M is the
    // advertised scaling ceiling, not a single initial funded size.
    slug: "the5ers",
    name: "The5%ers",
    rank: 3,
    rating: 4.6,
    legalEntity: undefined, // NULL — not primary-confirmable; see NOTE
    hq: "Ra'anana, Israel",
    ceo: undefined, // NULL — not primary-confirmable; see NOTE
    incorporated: "2016",
    summary:
      "The5%ers is an Israel-based forex proprietary trading firm (est. 2016) offering simulated evaluation programs (Hyper Growth, High Stakes, Bootcamp) that lead to funded accounts scaling up to $4 million.",
    reviewBody:
      "## Overview\n\nThe5%ers is one of the longest-running firms in the industry, founded in 2016. Its programs — Hyper Growth (one-step), High Stakes (two-step), and Bootcamp (three-step) — run on MT5, cTrader, and TradingView.\n\n## Funding & splits\n\nEntry starts around $2,500 (High Stakes), with an advertised scaling ceiling up to $4,000,000 and profit splits up to 100%. The firm emphasises low-risk, consistent trading.\n\n" + VERIFIED,
    platforms: "MT5,cTrader,TradingView",
    websiteUrl: "https://the5ers.com",
    affiliateUrl: "https://the5ers.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "three-step"],
    plans: [
      { challenge: "One-step", minAccount: 2500, maxAccount: 4000000, profitSplit: 100 },
      { challenge: "Two-step", minAccount: 2500, maxAccount: 4000000, profitSplit: 100 },
      { challenge: "Three-step", minAccount: 2500, maxAccount: 4000000, profitSplit: 100 },
    ],
    coupon: { code: COUPON_CODE, percent: 10, note: "10% off challenges" },
  },
  {
    slug: "ftmo",
    name: "FTMO",
    rank: 4,
    rating: 4.7,
    legalEntity: "FTMO s.r.o.",
    hq: "Prague, Czech Republic",
    ceo: "Otakar Šuffner",
    incorporated: "2015",
    summary:
      "FTMO is a Prague-based proprietary trading firm (est. 2015) offering one-step and two-step simulated evaluations that grant funded accounts up to $200,000, with a scaling plan to grow capital and profit split.",
    reviewBody:
      "## Overview\n\nFTMO (FTMO s.r.o., Prague) popularised the two-step evaluation model and remains the most recognised name in the space since 2015. It supports MT4, MT5, and cTrader.\n\n## Funding & splits\n\nFunded accounts run from $10,000 to $200,000 with a base 80% split scaling to 90%; capital can grow beyond $200K via the scaling plan. Known for strong infrastructure and reliable payouts.\n\n" + VERIFIED,
    platforms: "MT4,MT5,cTrader",
    websiteUrl: "https://ftmo.com",
    affiliateUrl: "https://ftmo.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "Two-step", minAccount: 10000, maxAccount: 200000, profitSplit: 90 },
      { challenge: "One-step", minAccount: 10000, maxAccount: 200000, profitSplit: 90 },
    ],
    // No coupon (firm does not run a forexpropreviews discount code).
  },
  {
    // NOTE: Hong Kong registration CONFIRMED via primary source
    // (holaprime.com/about-us, Jun 2026): "Hola Prime Limited, a company
    // registered at L1, Shaw House, 201 Wan Po Road, Tseung Kwan O, Hong Kong"
    // (Cyprus HE 454359 and a Mauritius entity are also disclosed). CEO is NULL:
    // the About page names no CEO; "Somesh Kapuria" was secondary-only and is
    // not primary-confirmable. incorporated "August 2024" is also secondary.
    slug: "hola-prime",
    name: "Hola Prime",
    rank: 5,
    rating: 4.5,
    legalEntity: "Hola Prime Limited",
    hq: "Hong Kong",
    ceo: undefined, // NULL — not named on primary source; see NOTE
    incorporated: "August 2024",
    summary:
      "Hola Prime is a forex/CFD proprietary trading firm registered in Hong Kong (Aug 2024) offering one-step, two-step, and instant (Direct) funding across MT4/MT5, cTrader, Match-Trader and DXTrade, with funded accounts up to $300,000.",
    reviewBody:
      "## Overview\n\nHola Prime (Hola Prime Limited, Hong Kong, with a Dubai office) launched in August 2024 and grew fast on the back of flexible evaluations and rapid payout claims. It supports MT4, MT5, cTrader, Match-Trader, and DXTrade.\n\n## Funding & splits\n\nOne-step, two-step, and instant (Direct) models run from $5,000 up to $300,000, scaling toward ~$4M, with profit splits up to 95%.\n\n" + VERIFIED,
    platforms: "MT4,MT5,cTrader,Match-Trader,DXTrade",
    websiteUrl: "https://holaprime.com",
    affiliateUrl: "https://holaprime.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "instant"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 300000, profitSplit: 95 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 300000, profitSplit: 95 },
      { challenge: "Instant", minAccount: 5000, maxAccount: 300000, profitSplit: 95 },
    ],
    coupon: { code: COUPON_CODE, percent: 15, note: "15% off challenges" },
  },
  {
    // NOTE: LOW CONFIDENCE — no primary source obtainable. e8markets.com returns
    // HTTP 403 and official LinkedIn is login-walled (Jun 2026), so legalEntity,
    // CEO, incorporation date and HQ are set NULL. ALL remaining E8 facts below
    // (platforms, account sizes, challenge models) are secondary-source only and
    // unverified — confirm directly with the firm before relying on them.
    slug: "e8-markets",
    name: "E8 Markets",
    rank: 6,
    rating: 4.4,
    legalEntity: undefined, // NULL — no primary source (site 403); see NOTE
    hq: undefined, // NULL — no primary source (site 403); see NOTE
    ceo: undefined, // NULL — no primary source (site 403); see NOTE
    incorporated: undefined, // NULL — no primary source (site 403); see NOTE
    summary:
      "E8 Markets (rebranded from E8 Funding) is a proprietary trading firm offering one-step (E8 One) and multi-step (E8 Signature) evaluations with funded accounts up to $500,000. Company-registration and leadership details could not be verified from a primary source.",
    reviewBody:
      "## Overview\n\nE8 Markets (rebranded from E8 Funding) is known for a configurable evaluation and polished trader dashboard. Secondary sources list MT5, cTrader, TradeLocker, and Match-Trader.\n\n## Funding & splits\n\nOne-step (E8 One) and two-step (E8 Signature) tracks run from $5,000 up to $500,000, scaling beyond $1M, with splits up to 100% on E8 One (performance-tied; standard ~80%).\n\n_Note: E8's official site blocks automated access; company-registration, HQ and leadership details are unverified — confirm with the firm._",
    platforms: "MT5,cTrader,TradeLocker,Match-Trader",
    websiteUrl: "https://e8markets.com",
    affiliateUrl: "https://e8markets.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 500000, profitSplit: 100 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 500000, profitSplit: 80 },
    ],
    coupon: { code: COUPON_CODE, percent: 5, note: "5% off challenges" },
  },
  {
    slug: "fxify",
    name: "FXIFY",
    rank: 7,
    rating: 4.4,
    legalEntity: "FXIFY Markets Ltd (Labuan, Malaysia)",
    hq: "London, United Kingdom",
    ceo: "Peter Brown",
    incorporated: "2023",
    summary:
      "FXIFY is a broker-backed forex/CFD proprietary trading firm launched in 2023 that offers one-, two- and three-step evaluations plus instant funding, with funded capital up to $400,000.",
    reviewBody:
      "## Overview\n\nFXIFY, an early broker-backed prop firm, launched in 2023. Its registered broker entity is FXIFY Markets Ltd (Labuan, Malaysia) with London operations. Platforms include MT4, MT5, DXtrade, and TradingView (cTrader is not offered).\n\n## Funding & splits\n\nOne-step (Lightning), two-step, three-step, and instant funding run from $5,000 up to $400,000 with profit splits up to 90% (and add-on options).\n\n" + VERIFIED,
    platforms: "MT4,MT5,DXtrade,TradingView",
    websiteUrl: "https://fxify.com",
    affiliateUrl: "https://fxify.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "three-step", "instant"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
      { challenge: "Three-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
      { challenge: "Instant", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 15, note: "15% off challenges" },
  },
  {
    // NOTE: account max ambiguous — forex division historically tops out at
    // ~$200K; current site shows $400K largely via the futures division.
    slug: "blue-guardian",
    name: "Blue Guardian",
    rank: 8,
    rating: 4.3,
    legalEntity: "Iconic Exchange FZCO (Dubai, UAE)",
    hq: "Dubai, United Arab Emirates",
    ceo: "Sean Bainton",
    incorporated: "September 2021",
    summary:
      "Blue Guardian is a UAE-based forex/CFD and futures proprietary trading firm founded in 2021 that offers one-, two-, and three-step evaluations plus instant-funding accounts.",
    reviewBody:
      "## Overview\n\nBlue Guardian (Iconic Exchange FZCO, Dubai) launched in 2021 with an emphasis on capital-preservation-friendly rules and a clean evaluation. It spans forex and futures, with MT5, Match-Trader, TradeLocker, Tradovate, and ProjectX.\n\n## Funding & splits\n\nOne-, two-, and three-step plus instant models run from $5,000 up to $400,000 (largest sizes via the futures division), with profit splits up to 90%.\n\n" + VERIFIED,
    platforms: "MT5,Match-Trader,TradeLocker,Tradovate,ProjectX",
    websiteUrl: "https://blueguardian.com",
    affiliateUrl: "https://blueguardian.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "three-step", "instant"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
      { challenge: "Three-step", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
      { challenge: "Instant", minAccount: 5000, maxAccount: 400000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 35, note: "35% off challenges" },
  },
  {
    // NOTE: CEO is NULL. Primary check (funderpro.com/about-us, Jun 2026) still
    // states "Gary is the Co-Founder and CEO of FunderPro" (Gary Mullen). The
    // secondary claim that Tim Plummer took over on 2026-06-26 (FX News Group)
    // could NOT be confirmed from any primary source, so the field is left null.
    // legalEntity below remains secondary (terms page was unreachable / 404).
    slug: "funderpro",
    name: "FunderPro",
    rank: 9,
    rating: 4.3,
    legalEntity: "FUNDERPRO Ltd (Malta)",
    hq: "St Julian's, Malta",
    ceo: undefined, // NULL — not primary-confirmable; see NOTE
    incorporated: "2023",
    summary:
      "FunderPro is a Malta-based forex/CFD proprietary trading firm, part of the Deus X Capital group, offering simulated-capital evaluations across one-phase, two-phase and instant funding models.",
    reviewBody:
      "## Overview\n\nFunderPro (FUNDERPRO Ltd, Malta), part of the Deus X Capital group, launched in February 2023. It runs on MT5, cTrader, and TradeLocker and positions itself as a transparent, broker-backed option.\n\n## Funding & splits\n\nOne-phase, two-phase, and instant funding run from $5,000 up to $200,000 with profit splits up to 90% (base 80%).\n\n" + VERIFIED,
    platforms: "MT5,cTrader,TradeLocker",
    websiteUrl: "https://funderpro.com",
    affiliateUrl: "https://funderpro.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "instant"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
      { challenge: "Instant", minAccount: 5000, maxAccount: 200000, profitSplit: 90 },
    ],
    coupon: { code: COUPON_CODE, percent: 10, note: "10% off challenges" },
  },
  {
    slug: "fintokei",
    name: "Fintokei",
    rank: 10,
    rating: 4.2,
    legalEntity: "Fintokei a.s. (part of Purple Group)",
    hq: "Brno, Czech Republic",
    ceo: "David Varga",
    incorporated: "2022",
    summary:
      "Fintokei is a forex/CFD proprietary trading evaluation firm operated by Czech entity Fintokei a.s. (part of the Purple Group), targeting the Japanese and broader Asian market with simulated-capital challenge programs.",
    reviewBody:
      "## Overview\n\nFintokei (Fintokei a.s., Brno, part of the Purple Group) launched in 2022 with a strong focus on the Japanese and wider Asian market, offering a polished, localised experience on MT5, cTrader, and TradingView.\n\n## Funding & splits\n\nMultiple tiers (incl. SwiftTrader and ProTrader) run from $5,000 up to $400,000, with profit splits up to 100% on the SwiftTrader program (others ~80%).\n\n" + VERIFIED,
    platforms: "MT5,cTrader,TradingView",
    websiteUrl: "https://fintokei.com",
    affiliateUrl: "https://fintokei.com/?ref=forexpropreviews",
    tagSlugs: ["one-step", "two-step", "three-step"],
    plans: [
      { challenge: "One-step", minAccount: 5000, maxAccount: 400000, profitSplit: 100 },
      { challenge: "Two-step", minAccount: 5000, maxAccount: 400000, profitSplit: 100 },
      { challenge: "Three-step", minAccount: 5000, maxAccount: 400000, profitSplit: 100 },
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
