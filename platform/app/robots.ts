import type { MetadataRoute } from "next";
import { absoluteUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // API routes are for the app's own use, not search engines.
      disallow: "/api/",
    },
    sitemap: absoluteUrl("/sitemap.xml"),
  };
}
