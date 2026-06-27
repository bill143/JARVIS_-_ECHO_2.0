"use client";

import { useRouter } from "next/navigation";

type FirmOption = { slug: string; name: string };

const selectClass =
  "w-full rounded-md border border-panel-edge bg-panel px-3 py-2 text-sm text-text focus-visible:outline-none focus-visible:border-accent";

export function ComparePicker({
  firms,
  a,
  b,
}: {
  firms: FirmOption[];
  a: string;
  b: string;
}) {
  const router = useRouter();

  function go(nextA: string, nextB: string) {
    const params = new URLSearchParams();
    if (nextA) params.set("a", nextA);
    if (nextB) params.set("b", nextB);
    router.push(`/compare?${params.toString()}`);
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <div>
        <label
          htmlFor="compare-a"
          className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
        >
          Firm A
        </label>
        <select
          id="compare-a"
          value={a}
          onChange={(e) => go(e.target.value, b)}
          className={selectClass}
        >
          <option value="">Select a firm…</option>
          {firms.map((f) => (
            <option key={f.slug} value={f.slug} disabled={f.slug === b}>
              {f.name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label
          htmlFor="compare-b"
          className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
        >
          Firm B
        </label>
        <select
          id="compare-b"
          value={b}
          onChange={(e) => go(a, e.target.value)}
          className={selectClass}
        >
          <option value="">Select a firm…</option>
          {firms.map((f) => (
            <option key={f.slug} value={f.slug} disabled={f.slug === a}>
              {f.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
