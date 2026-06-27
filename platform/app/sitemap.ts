import type { MetadataRoute } from "next";
import { getFirms } from "@/lib/firms";
import { absoluteUrl } from "@/lib/seo";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPaths = [
    "/",
    "/offers",
    "/compare",
    "/about",
    "/how-we-test",
    "/contact",
    "/privacy",
    "/terms",
  ];

  const now = new Date();
  const staticEntries: MetadataRoute.Sitemap = staticPaths.map((p) => ({
    url: absoluteUrl(p),
    lastModified: now,
    changeFrequency: "weekly",
    priority: p === "/" ? 1 : 0.7,
  }));

  const firms = await getFirms();
  const firmEntries: MetadataRoute.Sitemap = firms.map((f) => ({
    url: absoluteUrl(`/firms/${f.slug}`),
    lastModified: now,
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  return [...staticEntries, ...firmEntries];
}
