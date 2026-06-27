import { RatingStars } from "@/components/RatingStars";
import { DiscountBadge } from "@/components/DiscountBadge";
import { formatAccountRange } from "@/lib/format";
import type { FirmDTO } from "@/lib/types";
import type { ReactNode } from "react";

type Row = {
  label: string;
  render: (firm: FirmDTO) => ReactNode;
};

const ROWS: Row[] = [
  { label: "Rank", render: (f) => (f.rank != null ? `#${f.rank}` : "—") },
  { label: "Rating", render: (f) => <RatingStars rating={f.rating} /> },
  {
    label: "Top discount",
    render: (f) => (
      <DiscountBadge percent={f.topDiscount} note={f.coupons[0]?.note} />
    ),
  },
  {
    label: "Coupon code",
    render: (f) => (
      <span className="font-mono">{f.coupons[0]?.code ?? "—"}</span>
    ),
  },
  { label: "Legal entity", render: (f) => f.legalEntity ?? "—" },
  { label: "Headquarters", render: (f) => f.hq ?? "—" },
  { label: "CEO", render: (f) => f.ceo ?? "—" },
  { label: "Incorporated", render: (f) => f.incorporated ?? "—" },
  {
    label: "Account range",
    render: (f) => formatAccountRange(f.minAccount, f.maxAccount),
  },
  {
    label: "Platforms",
    render: (f) => f.platforms.join(", ") || "—",
  },
  {
    label: "Challenge types",
    render: (f) => f.tags.map((t) => t.label).join(", ") || "—",
  },
  {
    label: "Profit split",
    render: (f) => {
      const splits = f.plans
        .map((p) => p.profitSplit)
        .filter((s): s is number => typeof s === "number");
      return splits.length ? `Up to ${Math.max(...splits)}%` : "—";
    },
  },
  { label: "Liquidity", render: (f) => f.liquidity ?? "—" },
];

export function CompareTable({ a, b }: { a: FirmDTO; b: FirmDTO }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-panel-edge bg-panel">
      <table className="w-full min-w-[560px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className="px-3 py-3 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
              Field
            </th>
            {[a, b].map((firm) => (
              <th
                key={firm.id}
                scope="col"
                className="px-3 py-3 text-left text-base font-bold text-text"
              >
                {firm.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.label} className="border-b border-line last:border-0">
              <th
                scope="row"
                className="px-3 py-3 text-left font-mono text-[11px] uppercase tracking-wide text-muted"
              >
                {row.label}
              </th>
              <td className="px-3 py-3 text-text">{row.render(a)}</td>
              <td className="px-3 py-3 text-text">{row.render(b)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
