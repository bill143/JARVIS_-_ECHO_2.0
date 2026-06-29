import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { pageMetadata, SITE_NAME } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Terms of Use",
  description: `The terms governing your use of ${SITE_NAME}.`,
  path: "/terms",
});

export default function TermsPage() {
  return (
    <div>
      <PageHeader eyebrow="Legal" title="Terms of Use" />
      <div className="prose-review max-w-2xl text-text">
        <p>
          This is a placeholder terms-of-use document for the MVP. Replace it
          with reviewed terms before launch.
        </p>
        <h2>No financial advice</h2>
        <p>
          Content on {SITE_NAME} is for informational purposes only and is not
          financial advice. Trading carries substantial risk of loss.
        </p>
        <h2>Accuracy</h2>
        <p>
          We strive for accuracy, but firm terms, pricing, and discounts change
          frequently. Always confirm details on the firm&apos;s own site.
        </p>
        <h2>Affiliate relationships</h2>
        <p>
          We may earn commissions from links on this site. This does not affect
          our independent ratings.
        </p>
        <h2>Limitation of liability</h2>
        <p>
          We are not liable for any losses arising from decisions made based on
          information found on this site.
        </p>
      </div>
    </div>
  );
}
