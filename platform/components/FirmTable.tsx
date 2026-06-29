"use client";

import Link from "next/link";
import { RatingStars } from "@/components/RatingStars";
import { DiscountBadge } from "@/components/DiscountBadge";
import { Button } from "@/components/ui";
import { formatAccountRange } from "@/lib/format";
import type { FirmDTO } from "@/lib/types";
import type { SortKey } from "@/components/DirectoryClient";

const headerCellClass =
  "px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted";

function SortButton({
  label,
  sortKey,
  activeKey,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  activeKey: SortKey;
  onSort: (key: SortKey) => void;
}) {
  const active = activeKey === sortKey;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      aria-pressed={active}
      className={`inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-wide transition-colors hover:text-accent ${
        active ? "text-accent" : "text-muted"
      }`}
    >
      {label}
      <span aria-hidden="true">{active ? "▾" : ""}</span>
    </button>
  );
}

export function FirmTable({
  firms,
  sortKey,
  onSort,
}: {
  firms: FirmDTO[];
  sortKey: SortKey;
  onSort: (key: SortKey) => void;
}) {
  if (firms.length === 0) {
    return (
      <div className="rounded-lg border border-panel-edge bg-panel p-8 text-center text-muted">
        No firms match your filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-panel-edge bg-panel">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <caption className="sr-only">
          Ranked list of prop trading firms, sortable by rank, rating, and
          discount.
        </caption>
        <thead>
          <tr className="border-b border-line">
            <th scope="col" className={headerCellClass}>
              <SortButton
                label="Rank"
                sortKey="rank"
                activeKey={sortKey}
                onSort={onSort}
              />
            </th>
            <th scope="col" className={headerCellClass}>
              Firm
            </th>
            <th scope="col" className={headerCellClass}>
              <SortButton
                label="Rating"
                sortKey="rating"
                activeKey={sortKey}
                onSort={onSort}
              />
            </th>
            <th scope="col" className={headerCellClass}>
              <SortButton
                label="Discount"
                sortKey="discount"
                activeKey={sortKey}
                onSort={onSort}
              />
            </th>
            <th scope="col" className={headerCellClass}>
              Accounts
            </th>
            <th scope="col" className={headerCellClass}>
              Platforms
            </th>
            <th scope="col" className={`${headerCellClass} text-right`}>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {firms.map((firm) => (
            <tr
              key={firm.id}
              className="border-b border-line last:border-0 hover:bg-bg"
            >
              <td className="px-3 py-3 font-mono font-bold text-accent">
                {firm.rank ?? "—"}
              </td>
              <td className="px-3 py-3">
                <Link
                  href={`/firms/${firm.slug}`}
                  className="flex items-center gap-2 font-medium text-text hover:text-accent"
                >
                  <span
                    aria-hidden="true"
                    className="flex h-7 w-7 items-center justify-center rounded border border-line bg-bg font-mono text-[11px] text-muted"
                  >
                    {firm.name.slice(0, 2).toUpperCase()}
                  </span>
                  {firm.name}
                </Link>
              </td>
              <td className="px-3 py-3">
                <RatingStars rating={firm.rating} showValue={false} />
                <span className="ml-1 font-mono text-xs text-muted">
                  {firm.rating?.toFixed(1) ?? "—"}
                </span>
              </td>
              <td className="px-3 py-3">
                <DiscountBadge
                  percent={firm.topDiscount}
                  note={firm.coupons[0]?.note}
                />
              </td>
              <td className="px-3 py-3 font-mono text-xs text-text">
                {formatAccountRange(firm.minAccount, firm.maxAccount)}
              </td>
              <td className="px-3 py-3 text-xs text-muted">
                {firm.platforms.join(", ") || "—"}
              </td>
              <td className="px-3 py-3">
                <div className="flex justify-end gap-2">
                  <Button
                    href={`/firms/${firm.slug}`}
                    variant="ghost"
                    className="px-2.5 py-1.5 text-xs"
                  >
                    Review
                  </Button>
                  {firm.affiliateUrl && (
                    <Button
                      href={firm.affiliateUrl}
                      external
                      className="px-2.5 py-1.5 text-xs"
                    >
                      Visit
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
