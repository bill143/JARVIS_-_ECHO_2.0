import { RatingStars } from "@/components/RatingStars";
import { DiscountBadge } from "@/components/DiscountBadge";
import { Button, Tag } from "@/components/ui";
import { formatAccountRange } from "@/lib/format";
import type { FirmDTO } from "@/lib/types";

// Used on mobile (the FirmTable degrades to cards). Also reusable elsewhere.
export function FirmCard({ firm }: { firm: FirmDTO }) {
  return (
    <article className="rounded-lg border border-panel-edge bg-panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-bg font-mono text-sm font-bold text-accent"
          >
            #{firm.rank ?? "—"}
          </span>
          <div>
            <h3 className="font-semibold text-text">{firm.name}</h3>
            <RatingStars rating={firm.rating} />
          </div>
        </div>
        <DiscountBadge percent={firm.topDiscount} note={firm.coupons[0]?.note} />
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-muted">
            Accounts
          </dt>
          <dd className="text-text">
            {formatAccountRange(firm.minAccount, firm.maxAccount)}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[11px] uppercase tracking-wide text-muted">
            Platforms
          </dt>
          <dd className="text-text">{firm.platforms.join(", ") || "—"}</dd>
        </div>
      </dl>

      {firm.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {firm.tags.map((t) => (
            <Tag key={t.id}>{t.label}</Tag>
          ))}
        </div>
      )}

      <div className="mt-4 flex gap-2">
        <Button href={`/firms/${firm.slug}`} variant="ghost" className="flex-1">
          Review
        </Button>
        {firm.affiliateUrl && (
          <Button href={firm.affiliateUrl} external className="flex-1">
            Visit
          </Button>
        )}
      </div>
    </article>
  );
}
