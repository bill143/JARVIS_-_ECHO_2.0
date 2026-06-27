import type { Metadata } from "next";
import { getOffers } from "@/lib/firms";
import { OffersClient } from "@/components/OffersClient";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Prop Firm Offers & Coupon Codes",
  description:
    "Active discounts and coupon codes across the best forex prop firms. Copy a code and claim the offer.",
  path: "/offers",
});

export default async function OffersPage() {
  const offers = await getOffers();

  return (
    <div>
      <header className="mb-6">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
          Save on your challenge
        </p>
        <h1 className="mb-2 text-3xl font-bold tracking-tight text-text">
          Offers &amp; Coupons
        </h1>
        <p className="max-w-2xl text-muted">
          Current discounts across the firms we review. Codes and offers change
          frequently — always confirm on the firm&apos;s site at checkout.
        </p>
      </header>

      <OffersClient offers={offers} />
    </div>
  );
}
