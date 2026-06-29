"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" ? "light" : "dark";
}

export function ThemeToggle() {
  // Mirror the attribute the inline ThemeScript already set, so there is no
  // flash and no hydration mismatch (we only read after mount).
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTheme(getInitialTheme());
    setMounted(true);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* ignore storage errors (e.g. private mode) */
    }
  }

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
      aria-pressed={isDark}
      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-panel-edge bg-panel text-text transition-colors hover:border-accent"
      // Avoid showing a potentially-wrong icon before we've read the attribute.
      suppressHydrationWarning
    >
      <span aria-hidden="true" className="text-base">
        {mounted ? (isDark ? "☀" : "☾") : "☾"}
      </span>
    </button>
  );
}
