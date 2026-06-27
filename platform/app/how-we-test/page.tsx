import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "How We Test",
  description:
    "Our methodology for testing and rating proprietary trading firms — the criteria behind every rating.",
  path: "/how-we-test",
});

const CRITERIA: { name: string; detail: string }[] = [
  {
    name: "Payout reliability",
    detail:
      "We track real payout reports and, where possible, request payouts ourselves to confirm timelines and conditions.",
  },
  {
    name: "Evaluation fairness",
    detail:
      "We assess targets, drawdown rules, time limits, and consistency rules across each firm's challenge models.",
  },
  {
    name: "Pricing & value",
    detail:
      "We compare challenge fees, refunds, and discounts relative to account size and profit split.",
  },
  {
    name: "Platform & execution",
    detail:
      "We check supported platforms (MT4/MT5/cTrader/Match-Trader), spreads, and execution quality.",
  },
  {
    name: "Transparency",
    detail:
      "We verify the legal entity, registration, leadership, and the clarity of the firm's terms.",
  },
  {
    name: "Support & reputation",
    detail:
      "We evaluate support responsiveness and the firm's standing across independent trader communities.",
  },
];

export default function HowWeTestPage() {
  return (
    <div>
      <PageHeader eyebrow="Methodology" title="How We Test">
        Every rating on this site comes from a consistent set of criteria. Here
        is exactly what we look at.
      </PageHeader>

      <ol className="space-y-4">
        {CRITERIA.map((c, i) => (
          <li
            key={c.name}
            className="rounded-lg border border-panel-edge bg-panel p-5"
          >
            <div className="flex items-start gap-3">
              <span className="flex h-7 w-7 flex-none items-center justify-center rounded-md border border-line bg-bg font-mono text-sm font-bold text-accent">
                {i + 1}
              </span>
              <div>
                <h2 className="font-semibold text-text">{c.name}</h2>
                <p className="mt-1 text-sm text-muted">{c.detail}</p>
              </div>
            </div>
          </li>
        ))}
      </ol>

      <p className="mt-6 max-w-2xl text-sm text-muted">
        Ratings are reviewed periodically and updated when a firm&apos;s terms,
        pricing, or reliability change. {/* TODO: link to scoring rubric. */}
      </p>
    </div>
  );
}
