import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getFirms, getFirmBySlug } from "@/lib/firms";
import { RatingStars } from "@/components/RatingStars";
import { DiscountBadge } from "@/components/DiscountBadge";
import { Button, Tag, Section } from "@/components/ui";
import { formatAccountRange, formatMoney } from "@/lib/format";
import { firmJsonLd, pageMetadata, SITE_NAME } from "@/lib/seo";

// Pre-render every firm page at build time.
export async function generateStaticParams() {
  const firms = await getFirms();
  return firms.map((f) => ({ slug: f.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const firm = await getFirmBySlug(params.slug);
  if (!firm) return pageMetadata({ title: "Firm not found", path: "/" });
  return pageMetadata({
    title: `${firm.name} Review (2026)`,
    description:
      firm.summary ??
      `Our independent review of ${firm.name}: ratings, plans, platforms and discounts.`,
    path: `/firms/${firm.slug}`,
  });
}

// Minimal, safe markdown-ish renderer for the seeded review bodies (headings,
// blockquotes, paragraphs). Keeps us from pulling in a markdown dependency.
function ReviewBody({ body }: { body: string }) {
  const blocks = body.split("\n\n");
  return (
    <div className="prose-review max-w-none text-text">
      {blocks.map((block, i) => {
        const trimmed = block.trim();
        if (trimmed.startsWith("## ")) {
          return <h2 key={i}>{trimmed.slice(3)}</h2>;
        }
        if (trimmed.startsWith("> ")) {
          return <blockquote key={i}>{trimmed.slice(2)}</blockquote>;
        }
        return <p key={i}>{trimmed}</p>;
      })}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="border-b border-line py-2 last:border-0">
      <dt className="font-mono text-[11px] uppercase tracking-wide text-muted">
        {label}
      </dt>
      <dd className="text-text">{value ?? "—"}</dd>
    </div>
  );
}

export default async function FirmPage({
  params,
}: {
  params: { slug: string };
}) {
  const firm = await getFirmBySlug(params.slug);
  if (!firm) notFound();

  const coupon = firm.coupons[0];
  const jsonLd = firmJsonLd(firm);

  return (
    <article>
      {/* JSON-LD AggregateRating / Review for rich results. */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-muted">
        <a href="/" className="hover:text-accent">
          Best 10
        </a>{" "}
        / <span className="text-text">{firm.name}</span>
      </nav>

      <header className="mb-8 rounded-lg border border-panel-edge bg-panel p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <span
              aria-hidden="true"
              className="flex h-14 w-14 items-center justify-center rounded-lg border border-line bg-bg font-mono text-lg font-bold text-accent"
            >
              {firm.name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <div className="flex items-center gap-2">
                {firm.rank != null && (
                  <span className="rounded border border-line bg-bg px-2 py-0.5 font-mono text-xs text-muted">
                    Rank #{firm.rank}
                  </span>
                )}
              </div>
              <h1 className="mt-1 text-2xl font-bold text-text sm:text-3xl">
                {firm.name} Review
              </h1>
              <div className="mt-1">
                <RatingStars rating={firm.rating} />
              </div>
            </div>
          </div>
          <DiscountBadge percent={firm.topDiscount} note={coupon?.note} />
        </div>

        {firm.summary && (
          <p className="mt-4 max-w-3xl text-muted">{firm.summary}</p>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          {firm.tags.map((t) => (
            <Tag key={t.id}>{t.label}</Tag>
          ))}
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          {firm.affiliateUrl && (
            <Button href={firm.affiliateUrl} external>
              Visit {firm.name}
            </Button>
          )}
          <Button href={`/compare?a=${firm.slug}`} variant="ghost">
            Compare
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Section title="Review" eyebrow="In depth">
            {firm.reviewBody ? (
              <ReviewBody body={firm.reviewBody} />
            ) : (
              <p className="text-muted">Review coming soon.</p>
            )}
          </Section>

          <Section title="Plans" eyebrow="Evaluation">
            <div className="overflow-x-auto rounded-lg border border-panel-edge bg-panel">
              <table className="w-full min-w-[480px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-line">
                    <th className="px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
                      Challenge
                    </th>
                    <th className="px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
                      Min account
                    </th>
                    <th className="px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
                      Max account
                    </th>
                    <th className="px-3 py-2 text-left font-mono text-[11px] uppercase tracking-wide text-muted">
                      Profit split
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {firm.plans.map((p) => (
                    <tr key={p.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-2 text-text">{p.challenge}</td>
                      <td className="px-3 py-2 font-mono text-text">
                        {formatMoney(p.minAccount)}
                      </td>
                      <td className="px-3 py-2 font-mono text-text">
                        {formatMoney(p.maxAccount)}
                      </td>
                      <td className="px-3 py-2 font-mono text-text">
                        {p.profitSplit != null ? `${p.profitSplit}%` : "—"}
                      </td>
                    </tr>
                  ))}
                  {firm.plans.length === 0 && (
                    <tr>
                      <td className="px-3 py-4 text-muted" colSpan={4}>
                        No plans listed.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Section>
        </div>

        <aside className="lg:col-span-1">
          <div className="rounded-lg border border-panel-edge bg-panel p-5">
            <h2 className="mb-3 font-mono text-xs uppercase tracking-widest text-accent">
              Firm facts
            </h2>
            <dl>
              <Fact label="Legal entity" value={firm.legalEntity} />
              <Fact label="Headquarters" value={firm.hq} />
              <Fact label="CEO" value={firm.ceo} />
              <Fact label="Incorporated" value={firm.incorporated} />
              <Fact label="Platforms" value={firm.platforms.join(", ") || null} />
              <Fact label="Liquidity" value={firm.liquidity} />
              <Fact
                label="Account range"
                value={formatAccountRange(firm.minAccount, firm.maxAccount)}
              />
              {coupon && (
                <Fact
                  label="Coupon code"
                  value={`${coupon.code}${
                    coupon.percent != null ? ` (${coupon.percent}% off)` : ""
                  }`}
                />
              )}
            </dl>
          </div>

          <p className="mt-4 text-xs text-muted">
            Reviews are produced independently by {SITE_NAME}. Some links are
            affiliate links — see our disclosure in the footer.
          </p>
        </aside>
      </div>
    </article>
  );
}
