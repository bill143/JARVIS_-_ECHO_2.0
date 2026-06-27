import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { SITE_NAME } from "@/lib/seo";

const NAV = [
  { href: "/", label: "Best 10" },
  { href: "/offers", label: "Offers" },
  { href: "/compare", label: "Compare" },
  { href: "/how-we-test", label: "How We Test" },
];

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-panel">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link
          href="/"
          className="flex items-center gap-2 font-bold text-text"
          aria-label={`${SITE_NAME} home`}
        >
          <span className="font-mono text-accent">▮</span>
          <span className="tracking-tight">{SITE_NAME}</span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-1 sm:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-md px-3 py-2 text-sm text-muted transition-colors hover:bg-bg hover:text-text"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
        </div>
      </div>

      {/* Mobile nav */}
      <nav
        aria-label="Primary mobile"
        className="flex items-center gap-1 overflow-x-auto border-t border-line px-2 py-1.5 sm:hidden"
      >
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="whitespace-nowrap rounded-md px-3 py-1.5 text-sm text-muted hover:text-text"
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
