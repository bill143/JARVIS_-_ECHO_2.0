import Link from "next/link";
import { SITE_NAME } from "@/lib/seo";

const COLS: { heading: string; links: { href: string; label: string }[] }[] = [
  {
    heading: "Reviews",
    links: [
      { href: "/", label: "Best 10 Firms" },
      { href: "/offers", label: "Offers & Coupons" },
      { href: "/compare", label: "Compare Firms" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/about", label: "About" },
      { href: "/how-we-test", label: "How We Test" },
      { href: "/contact", label: "Contact" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { href: "/privacy", label: "Privacy Policy" },
      { href: "/terms", label: "Terms of Use" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-panel">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2 font-bold text-text">
              <span className="font-mono text-accent">▮</span>
              <span>{SITE_NAME}</span>
            </div>
            <p className="mt-2 text-sm text-muted">
              Independent prop firm reviews and comparisons.
            </p>
          </div>
          {COLS.map((col) => (
            <div key={col.heading}>
              <h3 className="mb-3 font-mono text-xs uppercase tracking-widest text-muted">
                {col.heading}
              </h3>
              <ul className="space-y-2">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      className="text-sm text-text hover:text-accent"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* FTC affiliate disclosure (required, visible in footer). */}
        <p className="mt-8 border-t border-line pt-6 text-xs leading-relaxed text-muted">
          <strong className="text-text">Affiliate disclosure:</strong> Some
          links on this site are affiliate links. If you sign up with a firm
          through one of these links, we may earn a commission at no extra cost
          to you. This never affects our ratings, which are based on our
          independent testing methodology. Trading involves substantial risk;
          past performance is not indicative of future results.
        </p>
        <p className="mt-4 text-xs text-muted">
          © {new Date().getFullYear()} {SITE_NAME}. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
