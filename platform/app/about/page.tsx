import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { pageMetadata, SITE_NAME } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "About",
  description: `About ${SITE_NAME} — who we are and how we review prop trading firms.`,
  path: "/about",
});

export default function AboutPage() {
  return (
    <div>
      <PageHeader eyebrow="Who we are" title="About" />
      <div className="prose-review max-w-2xl text-text">
        <p>
          {SITE_NAME} is an independent review site for proprietary trading
          firms. We test, compare, and rank the firms that fund retail traders,
          so you can choose the right one with confidence.
        </p>
        <h2>Independence</h2>
        <p>
          Our rankings are based on our own testing methodology. Some links on
          the site are affiliate links and may earn us a commission, but this
          never influences a firm&apos;s rating or placement. See our full
          affiliate disclosure in the footer.
        </p>
        <h2>What we cover</h2>
        <p>
          Evaluation models, pricing and discounts, payout reliability, platform
          support, and the legal entities behind each firm.
        </p>
        {/* TODO: extension point — team bios, editorial standards, contact links. */}
      </div>
    </div>
  );
}
