import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { pageMetadata, SITE_NAME } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Privacy Policy",
  description: `How ${SITE_NAME} handles your data.`,
  path: "/privacy",
});

export default function PrivacyPage() {
  return (
    <div>
      <PageHeader eyebrow="Legal" title="Privacy Policy" />
      <div className="prose-review max-w-2xl text-text">
        <p>
          This is a placeholder privacy policy for the MVP. Replace it with a
          reviewed policy before launch.
        </p>
        <h2>Information we collect</h2>
        <p>
          We collect only the information needed to operate the site, such as
          basic, anonymised analytics. We do not sell personal data.
        </p>
        <h2>Cookies</h2>
        <p>
          We store your theme preference in your browser&apos;s local storage.
          We may use cookies for analytics.
        </p>
        <h2>Affiliate links</h2>
        <p>
          When you click an affiliate link, the destination firm may set its own
          cookies. See our affiliate disclosure in the footer.
        </p>
        <h2>Contact</h2>
        <p>For privacy questions, use our contact page.</p>
      </div>
    </div>
  );
}
