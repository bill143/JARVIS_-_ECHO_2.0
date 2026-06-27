"use client";

import type { FirmFilters } from "@/components/DirectoryClient";

type Option = { value: string; label: string };

const ACCOUNT_OPTIONS: Option[] = [
  { value: "0", label: "Any account size" },
  { value: "10000", label: "$10k+" },
  { value: "50000", label: "$50k+" },
  { value: "100000", label: "$100k+" },
  { value: "200000", label: "$200k+" },
];

const DISCOUNT_OPTIONS: Option[] = [
  { value: "0", label: "Any discount" },
  { value: "5", label: "5%+" },
  { value: "10", label: "10%+" },
  { value: "20", label: "20%+" },
  { value: "30", label: "30%+" },
];

const selectClass =
  "w-full rounded-md border border-panel-edge bg-panel px-3 py-2 text-sm text-text focus-visible:outline-none focus-visible:border-accent";

export function Filters({
  filters,
  onChange,
  challengeOptions,
  platformOptions,
}: {
  filters: FirmFilters;
  onChange: (next: FirmFilters) => void;
  challengeOptions: string[];
  platformOptions: string[];
}) {
  function update<K extends keyof FirmFilters>(key: K, value: FirmFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <div className="rounded-lg border border-panel-edge bg-panel p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-1">
          <label
            htmlFor="filter-search"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Search firm
          </label>
          <input
            id="filter-search"
            type="search"
            value={filters.search}
            onChange={(e) => update("search", e.target.value)}
            placeholder="e.g. FTMO"
            className={selectClass}
          />
        </div>

        <div>
          <label
            htmlFor="filter-challenge"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Challenge type
          </label>
          <select
            id="filter-challenge"
            value={filters.challenge}
            onChange={(e) => update("challenge", e.target.value)}
            className={selectClass}
          >
            <option value="">All challenge types</option>
            {challengeOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filter-platform"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Platform
          </label>
          <select
            id="filter-platform"
            value={filters.platform}
            onChange={(e) => update("platform", e.target.value)}
            className={selectClass}
          >
            <option value="">All platforms</option>
            {platformOptions.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filter-account"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Account size
          </label>
          <select
            id="filter-account"
            value={String(filters.minAccount)}
            onChange={(e) => update("minAccount", Number(e.target.value))}
            className={selectClass}
          >
            {ACCOUNT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filter-discount"
            className="mb-1 block font-mono text-[11px] uppercase tracking-wide text-muted"
          >
            Min discount
          </label>
          <select
            id="filter-discount"
            value={String(filters.minDiscount)}
            onChange={(e) => update("minDiscount", Number(e.target.value))}
            className={selectClass}
          >
            {DISCOUNT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
