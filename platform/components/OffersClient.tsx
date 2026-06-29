"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui";
import { DiscountBadge } from "@/components/DiscountBadge";
import { formatDate } from "@/lib/format";
import type { OfferDTO } from "@/lib/types";

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable; ignore */
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="inline-flex items-center gap-2 rounded-md border border-panel-edge bg-bg px-3 py-2 font-mono text-sm text-text transition-colors hover:border-accent"
      aria-label={`Copy coupon code ${code}`}
    >
      <span>{code}</span>
      <span className="text-accent">{copied ? "Copied!" : "Copy"}</span>
    </button>
  );
}

const selectClass =
  "rounded-md border border-panel-edge bg-panel px-3 py-2 text-sm text-text focus-visible:outline-none focus-visible:border-accent";

export function OffersClient({ offers }: { offers: OfferDTO[] }) {
  const [firmFilter, setFirmFilter] = useState("");
  const [minDiscount, setMinDiscount] = useState(0);

  const firmOptions = useMemo(
    () =>
      Array.from(new Set(offers.map((o) => o.firmName))).sort((a, b) =>
        a.localeCompare(b),
      ),
    [offers],
  );

  const visible = useMemo(
    () =>
      offers.filter((o) => {
        if (firmFilter && o.firmName !== firmFilter) return false;
        if (minDiscount > 0 && (o.percent ?? 0) < minDiscount) return false;
        return true;
      }),
    [offers, firmFilter, minDiscount],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-panel-edge bg-panel p-4">
        <div>
          <label
            htmlFor="offer-firm"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Firm
          </label>
          <select
            id="offer-firm"
            value={firmFilter}
            onChange={(e) => setFirmFilter(e.target.value)}
            className={selectClass}
          >
            <option value="">All firms</option>
            {firmOptions.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label
            htmlFor="offer-discount"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Min discount
          </label>
          <select
            id="offer-discount"
            value={String(minDiscount)}
            onChange={(e) => setMinDiscount(Number(e.target.value))}
            className={selectClass}
          >
            <option value="0">Any</option>
            <option value="5">5%+</option>
            <option value="10">10%+</option>
            <option value="20">20%+</option>
            <option value="30">30%+</option>
          </select>
        </div>
      </div>

      <p className="font-mono text-xs text-muted" role="status" aria-live="polite">
        Showing {visible.length} of {offers.length} offers
      </p>

      {visible.length === 0 ? (
        <div className="rounded-lg border border-panel-edge bg-panel p-8 text-center text-muted">
          No offers match your filters.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((offer) => (
            <article
              key={offer.id}
              className="flex flex-col gap-3 rounded-lg border border-panel-edge bg-panel p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <Link
                  href={`/firms/${offer.firmSlug}`}
                  className="font-semibold text-text hover:text-accent"
                >
                  {offer.firmName}
                </Link>
                <DiscountBadge percent={offer.percent} note={offer.note} />
              </div>

              {offer.note && offer.percent != null && (
                <p className="text-sm text-muted">{offer.note}</p>
              )}

              <CopyButton code={offer.code} />

              <p className="font-mono text-[11px] uppercase tracking-wide text-muted">
                Expires: {formatDate(offer.expiresAt)}
              </p>

              {offer.affiliateUrl && (
                <Button href={offer.affiliateUrl} external className="mt-auto">
                  Claim offer
                </Button>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
