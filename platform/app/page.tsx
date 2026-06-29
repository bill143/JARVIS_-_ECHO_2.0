import { getFirms } from "@/lib/firms";
import { Tape } from "@/components/Tape";
import { DirectoryClient } from "@/components/DirectoryClient";
import { pageMetadata } from "@/lib/seo";
import type { Metadata } from "next";

export const metadata: Metadata = pageMetadata({
  title: "Best 10 Forex Prop Firms (2026)",
  description:
    "Our ranked directory of the best forex proprietary trading firms — compare ratings, challenge types, platforms, account sizes, and live discounts.",
  path: "/",
});

// Server Component: fetches data, hands a serialisable list to the client
// directory for interactive filtering/sorting.
export default async function HomePage() {
  const firms = await getFirms();

  const ratings = firms
    .map((f) => f.rating)
    .filter((r): r is number => typeof r === "number");
  const avgRating = ratings.length
    ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(1)
    : "—";
  const discounts = firms
    .map((f) => f.topDiscount)
    .filter((d): d is number => typeof d === "number");
  const bestDiscount = discounts.length ? `${Math.max(...discounts)}%` : "—";

  return (
    <div>
      <section className="mb-8">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
          Independent reviews
        </p>
        <h1 className="mb-3 text-3xl font-bold tracking-tight text-text sm:text-4xl">
          Best Forex Prop Firms
        </h1>
        <p className="max-w-2xl text-muted">
          A ranked, filterable directory of the top proprietary trading firms.
          Compare ratings, challenge models, platforms, account sizes, and the
          latest discounts — all in one place.
        </p>
      </section>

      <div className="mb-8">
        <Tape
          stats={[
            { label: "Firms reviewed", value: String(firms.length) },
            { label: "Avg rating", value: avgRating },
            { label: "Best discount", value: bestDiscount },
            { label: "Coupon", value: "FOREXPROPREVIEWS" },
          ]}
        />
      </div>

      <DirectoryClient firms={firms} />
    </div>
  );
}
