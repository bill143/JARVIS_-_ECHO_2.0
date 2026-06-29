/**
 * Seed script for the Prop Firm Review Platform.
 *
 * Identity facts (legalEntity, headquarters/hq, ceo, foundedYear/incorporated)
 * were verified Jun 2026 under a STRICT primary-source rule: a value is kept
 * only if confirmed on the firm's official domain, its official LinkedIn page,
 * or a government registry (UK Companies House, Malta Business Registry, etc.).
 * Anything not primary-confirmable is set to NULL — never a secondary value.
 * Each firm's `// VERIFY` comment records the verdict, source URL and HTTP
 * status, and distinguishes two NULL reasons:
 *   (a) NULL — primary source contradicts the secondary claim
 *   (b) NULL — primary source unreachable (HTTP 403/503/404 / login wall)
 *
 * Product fields (platforms, account sizes, profit split, challenge types) may
 * rest on secondary corroboration where the official site blocks automated
 * access; these are flagged in the relevant `// VERIFY` notes.
 *
 * Editorial ratings are intentionally NULL (see RATING note below).
 * Discount/coupon values come from the forexpropreviews.com ranking.
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
  // RATING: NULL for every firm — editorial ratings pending Bill's criteria;
  // placeholder scores removed (do not invent replacements).
  rating: number | null;
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

const PROVENANCE =
  "_Company facts verified Jun 2026 against primary sources where reachable; see source notes. Figures may change — confirm on the firm's own site._";

const FIRMS: SeedFirm[] = [
  {
    // VERIFY (Jun 2026): HQ Dubai + foundedYear 2022 confirmed-PRIMARY via official
    // LinkedIn (linkedin.com/company/fundingpips -> 200). legalEntity NULL —
    // primary unreachable (fundingpips.com 403/429; "Funding Pips Corp." secondary
    // only). ceo NULL — primary unreachable ("Khaled Ayesh" secondary only).
    slug: "fundingpips",
    name: "FundingPips",
    rank: 1,
    rating: null,
    legalEntity: undefined, // NULL — primary unreachable (site 403/429)
    hq: "Dubai, United Arab Emirates",
    ceo: undefined, // NULL — primary unreachable (site 403/429)
    incorporated: "2022",
    summary:
      "FundingPips is a Dubai-based forex/CFD proprietary trading firm founded in 2022, offering one-step, two-step, and instant (Zero) evaluation models on MT5, cTrader, and Match-Trader.",
    reviewBody:
      "## Overview\n\nFundingPips, based in Dubai and founded in 2022, became one of the most talked-about firms in the space, known for fast scaling and a trader-friendly evaluation. It runs one-step, two-step, and instant (Zero) models on MT5, cTrader, and Match-Trader.\n\n## Funding & splits\n\nFunded accounts run from $5,000 up to $100,000, scaling toward ~$2M, with profit splits reported up to 100% on certain payout structures.\n\n" +
      PROVENANCE,
    platforms: "MT5,Match-Trader,cTrader",
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
    // VERIFY (Jun 2026): HQ Ajman confirmed-PRIMARY (helpfutures.fundednext.com
    // -> 200); ceo "Syed Abdullah Jayed" confirmed-PRIMARY (official LinkedIn ->
    // 200). legalEntity NULL — primary unreachable (fundednext.com terms 503;
    // "GrowthNext F.Z.E." secondary only). foundedYear NULL — not stated on any
    // reachable primary source.
    slug: "fundednext",
    name: "FundedNext",
    rank: 2,
    rating: null,
    legalEntity: undefined, // NULL — primary unreachable (terms 503)
    hq: "Ajman, United Arab Emirates",
    ceo: "Syed Abdullah Jayed",
    incorporated: undefined, // NULL — not on any reachable primary source
    summary:
      "FundedNext is an Ajman (UAE)-based forex/CFD proprietary trading firm offering one-step, two-step, and instant funding models (Stellar series) on MT4, MT5, cTrader, and Match-Trader.",
    reviewBody:
      "## Overview\n\nFundedNext, headquartered in Ajman, UAE and led by CEO Syed Abdullah Jayed, has grown into one of the largest names in prop trading. Its Stellar series spans one-step, two-step, and instant funding on MT4, MT5, cTrader, and Match-Trader.\n\n## Funding & splits\n\nAccounts run from about $6,000 up to $200,000, scaling toward $4M, with profit splits up to 95%.\n\n" +
      PROVENANCE,
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
    // VERIFY (Jun 2026): legalEntity confirmed-PRIMARY via UK Companies House
    // (FIVE PERCENT ONLINE LTD, Co. No. 12553363 -> 200). hq = UK registered
    // office (London) per the same registry; operational HQ "Ra'anana, Israel"
    // is secondary only. ceo NULL — primary unreachable / none names a leader
    // (the5ers.com 503; LinkedIn 404; "Gil Ben-Hur" secondary only). foundedYear
    // NULL — registry shows UK incorporation 2020; firm-claimed "2016" secondary.
    slug: "the5ers",
    name: "The5%ers",
    rank: 3,
    rating: null,
    legalEntity: "Five Percent Online Ltd (UK Co. No. 12553363)",
    hq: "London, United Kingdom (registered office)",
    ceo: undefined, // NULL — primary unreachable (site 503, LinkedIn 404)
    incorporated: undefined, // NULL — "2016" secondary; registry shows 2020
    summary:
      "The5%ers is a long-running forex proprietary trading firm (UK entity Five Percent Online Ltd) offering evaluation programs — Hyper Growth, High Stakes and Bootcamp — that scale funded capital toward $4 million.",
    reviewBody:
      "## Overview\n\nThe5%ers is one of the longest-running firms in the industry. Its UK-registered entity is Five Percent Online Ltd (Companies House no. 12553363). Programs — Hyper Growth (one-step), High Stakes (two-step) and Bootcamp (three-step) — run on MT4 and MT5.\n\n## Funding & splits\n\nEntry starts around $2,500, with an advertised scaling ceiling up to $4,000,000 and profit splits up to 100%.\n\n" +
      PROVENANCE,
    platforms: "MT4,MT5",
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
    // VERIFY (Jun 2026): ALL identity fields confirmed-PRIMARY on ftmo.com —
    // legalEntity "FTMO s.r.o." + foundedYear 2015 (terms-and-conditions -> 200),
    // HQ Prague (contact -> 200), ceo "Otakar Šuffner" (about -> 200: "Otakar
    // Šuffner (CEO)").
    slug: "ftmo",
    name: "FTMO",
    rank: 4,
    rating: null,
    legalEntity: "FTMO s.r.o.",
    hq: "Prague, Czech Republic",
    ceo: "Otakar Šuffner",
    incorporated: "2015",
    summary:
      "FTMO is a Prague-based proprietary trading firm (FTMO s.r.o., est. 2015) offering one-step and two-step simulated evaluations that grant funded accounts up to $200,000, with a scaling plan to grow capital and profit split.",
    reviewBody:
      "## Overview\n\nFTMO (FTMO s.r.o., Prague), led by CEO Otakar Šuffner, popularised the two-step evaluation model and remains the most recognised name in the space since 2015. It supports MT4, MT5, and cTrader.\n\n## Funding & splits\n\nFunded accounts run from $10,000 to $200,000 with a base 80% split scaling to 90%; capital can grow beyond $200K via the scaling plan.\n\n" +
      PROVENANCE,
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
    // VERIFY (Jun 2026): legalEntity + HQ confirmed-PRIMARY on fxify.com footer
    // ("FXIFY Markets LTD", Labuan, Malaysia; License MB/22/0097 -> 200). ceo
    // NULL — secondary sources conflict (David Bhidey / Peter Brown), none
    // primary. foundedYear NULL — "2023" secondary only, not on reachable primary.
    slug: "fxify",
    name: "FXIFY",
    rank: 5,
    rating: null,
    legalEntity: "FXIFY Markets Ltd (Labuan, Malaysia; Lic. MB/22/0097)",
    hq: "Labuan, Malaysia",
    ceo: undefined, // NULL — secondary sources conflict; none primary
    incorporated: undefined, // NULL — "2023" secondary only
    summary:
      "FXIFY is a broker-backed forex/CFD proprietary trading firm (FXIFY Markets Ltd, Labuan, Malaysia) offering one-, two- and three-step evaluations plus instant funding, with funded capital up to $400,000.",
    reviewBody:
      "## Overview\n\nFXIFY is a broker-backed prop firm whose registered entity is FXIFY Markets Ltd (Labuan, Malaysia; money-broker licence MB/22/0097). Platforms include MT4, MT5, DXtrade, and TradingView.\n\n## Funding & splits\n\nOne-, two-, three-step and instant funding run from $5,000 up to $400,000 with profit splits up to 90%.\n\n" +
      PROVENANCE,
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
    // VERIFY (Jun 2026): no primary source obtainable. e8markets.com and its
    // help-center return HTTP 403, and official LinkedIn is login-walled, so
    // legalEntity, hq, ceo and foundedYear are NULL — primary unreachable.
    // Product fields below are secondary-only and conflicting across sources
    // (e.g. account sizes reported as $5k-$500k vs $25k-$250k) — unverified.
    slug: "e8-markets",
    name: "E8 Markets",
    rank: 6,
    rating: null,
    legalEntity: undefined, // NULL — primary unreachable (site 403)
    hq: undefined, // NULL — primary unreachable (site 403)
    ceo: undefined, // NULL — primary unreachable (site 403)
    incorporated: undefined, // NULL — primary unreachable (site 403)
    summary:
      "E8 Markets (rebranded from E8 Funding) is a proprietary trading firm offering one-step (E8 One) and multi-step (E8 Signature) evaluations with funded accounts up to $500,000. Company-registration and leadership details could not be verified from a primary source.",
    reviewBody:
      "## Overview\n\nE8 Markets (rebranded from E8 Funding) is known for a configurable evaluation and polished trader dashboard. Secondary sources list MT5, cTrader, TradeLocker, and Match-Trader.\n\n## Funding & splits\n\nOne-step (E8 One) and two-step (E8 Signature) tracks run up to $500,000, scaling beyond $1M, with splits up to 100% on E8 One (performance-tied; standard ~80%).\n\n_Note: E8's official site blocks automated access (HTTP 403); company-registration, HQ, leadership and the figures above are secondary/unverified — confirm with the firm._",
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
    // VERIFY (Jun 2026): legalEntity "Iconic Exchange FZCO t/a Blue Guardian"
    // + HQ (IFZA Business Park, Dubai) confirmed-PRIMARY
    // (blueguardian.com/terms-and-conditions -> 200); ceo "Sean Bainton"
    // confirmed-PRIMARY (about-us -> 200). foundedYear NULL — "2021" secondary only.
    slug: "blue-guardian",
    name: "Blue Guardian",
    rank: 7,
    rating: null,
    legalEntity: "Iconic Exchange FZCO (t/a Blue Guardian)",
    hq: "Dubai, United Arab Emirates",
    ceo: "Sean Bainton",
    incorporated: undefined, // NULL — "2021" secondary only
    summary:
      "Blue Guardian is a UAE-based forex/CFD and futures proprietary trading firm (Iconic Exchange FZCO) offering one-, two- and three-step evaluations plus instant-funding accounts.",
    reviewBody:
      "## Overview\n\nBlue Guardian (Iconic Exchange FZCO, Dubai), led by CEO Sean Bainton, emphasises capital-preservation-friendly rules and a clean evaluation. It spans forex and futures, with MT5, Match-Trader, TradeLocker, Tradovate, and ProjectX.\n\n## Funding & splits\n\nOne-, two- and three-step plus instant models run from $5,000 up to $400,000 (largest sizes via the futures division), with profit splits up to 90%.\n\n" +
      PROVENANCE,
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
    // VERIFY (Jun 2026): legalEntity "Fintokei a.s." (terms -> 200) + HQ Brno
    // (contact -> 200) + foundedYear 2022 (about-us timeline -> 200) all
    // confirmed-PRIMARY. ceo "David Varga" confirmed-PRIMARY as Co-founder on
    // about-us; the specific "CEO" title is corroborated by secondary sources only.
    slug: "fintokei",
    name: "Fintokei",
    rank: 8,
    rating: null,
    legalEntity: "Fintokei a.s.",
    hq: "Brno, Czech Republic",
    ceo: "David Varga",
    incorporated: "2022",
    summary:
      "Fintokei is a forex/CFD proprietary trading evaluation firm operated by Czech entity Fintokei a.s., targeting the Japanese and broader Asian market with simulated-capital challenge programs.",
    reviewBody:
      "## Overview\n\nFintokei (Fintokei a.s., Brno), co-founded by David Varga, launched in 2022 with a strong focus on the Japanese and wider Asian market, offering a polished, localised experience on MT5, cTrader, and TradingView.\n\n## Funding & splits\n\nMultiple tiers (incl. SwiftTrader and ProTrader) run from $5,000 up to $400,000, with profit splits up to 100% on the SwiftTrader program (others ~80%).\n\n" +
      PROVENANCE,
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
  {
    // VERIFY (Jun 2026): legalEntity "Hola Prime Limited" + HQ Hong Kong
    // confirmed-PRIMARY (holaprime.com/about-us -> 200). ceo NULL — About page
    // names no CEO ("Somesh Kapuria" secondary only). foundedYear NULL — not on
    // primary. Product fields below are secondary-sourced (not re-fetched).
    slug: "hola-prime",
    name: "Hola Prime",
    rank: 9,
    rating: null,
    legalEntity: "Hola Prime Limited",
    hq: "Hong Kong",
    ceo: undefined, // NULL — not named on primary source
    incorporated: undefined, // NULL — not on primary source
    summary:
      "Hola Prime is a forex/CFD proprietary trading firm registered in Hong Kong (Hola Prime Limited) offering one-step, two-step, and instant (Direct) funding across MT4/MT5, cTrader, Match-Trader and DXtrade, with funded accounts up to $300,000.",
    reviewBody:
      "## Overview\n\nHola Prime (Hola Prime Limited, Hong Kong, with a Dubai office) grew fast on the back of flexible evaluations and rapid payout claims. It supports MT4, MT5, cTrader, Match-Trader, and DXtrade.\n\n## Funding & splits\n\nOne-step, two-step, and instant (Direct) models run from $5,000 up to $300,000, scaling toward ~$4M, with profit splits up to 95% (product figures secondary-sourced).\n\n" +
      PROVENANCE,
    platforms: "MT4,MT5,cTrader,Match-Trader,DXtrade",
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
    // VERIFY (Jun 2026): legalEntity "FunderPro Ltd" (Malta, Co. No. C 104558) +
    // HQ San Gwann + ceo "Gary Mullen" all confirmed-PRIMARY (funderpro.com/
    // terms-conditions -> 200 and /about-us -> 200: "Gary is the Co-Founder and
    // CEO of FunderPro"). foundedYear NULL — "2022" secondary only. The earlier
    // secondary claim that Tim Plummer is CEO is NOT on funderpro.com.
    slug: "funderpro",
    name: "FunderPro",
    rank: 10,
    rating: null,
    legalEntity: "FunderPro Ltd (Malta, Co. No. C 104558)",
    hq: "San Gwann, Malta",
    ceo: "Gary Mullen",
    incorporated: undefined, // NULL — "2022" secondary only
    summary:
      "FunderPro is a Malta-based forex/CFD proprietary trading firm (FunderPro Ltd) offering simulated-capital evaluations across one-phase, two-phase and instant funding models.",
    reviewBody:
      "## Overview\n\nFunderPro (FunderPro Ltd, Malta; reg. C 104558), led by Co-Founder & CEO Gary Mullen, runs on MT5, cTrader, and TradeLocker and positions itself as a transparent, broker-backed option.\n\n## Funding & splits\n\nOne-phase, two-phase, and instant funding run from $5,000 up to $200,000 with profit splits up to 90% (base 80%).\n\n" +
      PROVENANCE,
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
