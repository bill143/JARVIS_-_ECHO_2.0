import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { pageMetadata, SITE_NAME } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Contact",
  description: `Get in touch with the ${SITE_NAME} team.`,
  path: "/contact",
});

const inputClass =
  "w-full rounded-md border border-panel-edge bg-panel px-3 py-2 text-sm text-text focus-visible:outline-none focus-visible:border-accent";

// NOTE: This form is intentionally non-functional for the MVP (no send).
// TODO: wire up to an email/CRM provider or a /api/contact route handler later.
export default function ContactPage() {
  return (
    <div>
      <PageHeader eyebrow="Get in touch" title="Contact">
        Questions, corrections, or partnership enquiries? Send us a message.
      </PageHeader>

      <form
        className="max-w-xl space-y-4 rounded-lg border border-panel-edge bg-panel p-6"
        aria-describedby="contact-note"
      >
        <div>
          <label
            htmlFor="contact-name"
            className="mb-1 block text-sm font-medium text-text"
          >
            Name
          </label>
          <input id="contact-name" name="name" type="text" className={inputClass} />
        </div>
        <div>
          <label
            htmlFor="contact-email"
            className="mb-1 block text-sm font-medium text-text"
          >
            Email
          </label>
          <input
            id="contact-email"
            name="email"
            type="email"
            className={inputClass}
          />
        </div>
        <div>
          <label
            htmlFor="contact-message"
            className="mb-1 block text-sm font-medium text-text"
          >
            Message
          </label>
          <textarea
            id="contact-message"
            name="message"
            rows={5}
            className={inputClass}
          />
        </div>
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg transition-colors hover:opacity-90"
        >
          Send message
        </button>
        <p id="contact-note" className="text-xs text-muted">
          This form is a styled demo for the MVP and does not send messages yet.
        </p>
      </form>
    </div>
  );
}
