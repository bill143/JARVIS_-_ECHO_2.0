import type { Metadata } from "next";
import { getFirms, getFirmBySlug } from "@/lib/firms";
import { CompareTable } from "@/components/CompareTable";
import { ComparePicker } from "@/components/ComparePicker";
import { Button } from "@/components/ui";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Compare Prop Firms Side by Side",
  description:
    "Compare any two forex prop firms side by side — ratings, discounts, account sizes, platforms, profit splits and more.",
  path: "/compare",
});

export default async function ComparePage({
  searchParams,
}: {
  searchParams: { a?: string; b?: string };
}) {
  const firms = await getFirms();
  const firmOptions = firms.map((f) => ({ slug: f.slug, name: f.name }));

  // Sensible defaults so the page is never empty: top two ranked firms.
  const aSlug = searchParams.a ?? firms[0]?.slug ?? "";
  const bSlug = searchParams.b ?? firms[1]?.slug ?? "";

  const [a, b] = await Promise.all([
    aSlug ? getFirmBySlug(aSlug) : Promise.resolve(null),
    bSlug ? getFirmBySlug(bSlug) : Promise.resolve(null),
  ]);

  return (
    <div>
      <header className="mb-6">
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
          Head to head
        </p>
        <h1 className="mb-2 text-3xl font-bold tracking-tight text-text">
          Compare Prop Firms
        </h1>
        <p className="max-w-2xl text-muted">
          Pick any two firms to see their key facts side by side.
        </p>
      </header>

      <div className="mb-6">
        <ComparePicker firms={firmOptions} a={aSlug} b={bSlug} />
      </div>

      {a && b ? (
        <CompareTable a={a} b={b} />
      ) : (
        <div className="rounded-lg border border-panel-edge bg-panel p-8 text-center text-muted">
          {aSlug === bSlug && aSlug
            ? "Please choose two different firms to compare."
            : "Select two firms above to compare them."}
          <div className="mt-4">
            <Button href="/" variant="ghost">
              Browse all firms
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
