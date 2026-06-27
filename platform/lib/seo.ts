import type { Metadata } from "next";
import type { FirmDTO } from "@/lib/types";

export const SITE_NAME = "ForexPropReviews";
export const SITE_DESCRIPTION =
  "Independent reviews and comparisons of the best forex proprietary trading firms — ratings, challenge types, platforms, and current discounts.";

export function siteUrl(): string {
  return process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
}

export function absoluteUrl(path: string): string {
  const base = siteUrl().replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export function pageMetadata(opts: {
  title: string;
  description?: string;
  path: string;
}): Metadata {
  const description = opts.description ?? SITE_DESCRIPTION;
  return {
    title: opts.title,
    description,
    alternates: { canonical: absoluteUrl(opts.path) },
    openGraph: {
      title: opts.title,
      description,
      url: absoluteUrl(opts.path),
      siteName: SITE_NAME,
      type: "website",
    },
    twitter: {
      card: "summary",
      title: opts.title,
      description,
    },
  };
}

/**
 * Build JSON-LD for a firm review page. Includes an `AggregateRating` and a
 * `Review` so the page is eligible for rich results.
 */
export function firmJsonLd(firm: FirmDTO): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: firm.name,
    description: firm.summary ?? SITE_DESCRIPTION,
    brand: { "@type": "Brand", name: firm.name },
    url: absoluteUrl(`/firms/${firm.slug}`),
    ...(firm.rating
      ? {
          aggregateRating: {
            "@type": "AggregateRating",
            ratingValue: firm.rating,
            bestRating: 5,
            worstRating: 1,
            ratingCount: 1,
          },
          review: {
            "@type": "Review",
            reviewRating: {
              "@type": "Rating",
              ratingValue: firm.rating,
              bestRating: 5,
              worstRating: 1,
            },
            author: { "@type": "Organization", name: SITE_NAME },
            reviewBody: firm.summary ?? "",
          },
        }
      : {}),
  };
}
