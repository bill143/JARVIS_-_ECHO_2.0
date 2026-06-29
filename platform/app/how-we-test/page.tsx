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

      <div className="mt-8 rounded-lg border border-panel-edge bg-panel p-5">
        <h2 className="font-semibold text-text">How the score is calculated</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          We do not invent ratings. Until our verified user-review system is
          live, each firm&apos;s score is a{" "}
          <strong className="text-text">
            transparent algorithmic composite
          </strong>{" "}
          of the verified hard attributes we hold for every firm — not opinion,
          and not user reviews:
        </p>
        <ul className="mt-3 max-w-2xl space-y-1.5 text-sm text-muted">
          <li>• Highest reward (profit) split — 30%</li>
          <li>• Current discount / value — 25%</li>
          <li>• Funded-capital scaling ceiling — 15%</li>
          <li>• Number of supported platforms — 15%</li>
          <li>• Range of challenge models offered — 15%</li>
        </ul>
        <p className="mt-3 max-w-2xl text-sm text-muted">
          Each factor is normalised across all firms and weighted as above. The
          six criteria listed earlier describe what we assess as real
          payout-proof and user-review data is gathered — at which point scores
          move from this provisional composite to verified, multi-criteria
          ratings. Scores update whenever a firm&apos;s verified terms or
          pricing change.
        </p>
      </div>
    </div>
  );
}
