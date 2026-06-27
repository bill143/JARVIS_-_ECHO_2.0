"use client";

import { useMemo, useState } from "react";
import { Filters } from "@/components/Filters";
import { FirmTable } from "@/components/FirmTable";
import { FirmCard } from "@/components/FirmCard";
import type { FirmDTO } from "@/lib/types";

export type SortKey = "rank" | "rating" | "discount";

export type FirmFilters = {
  search: string;
  challenge: string;
  platform: string;
  minAccount: number;
  minDiscount: number;
};

const DEFAULT_FILTERS: FirmFilters = {
  search: "",
  challenge: "",
  platform: "",
  minAccount: 0,
  minDiscount: 0,
};

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b));
}

export function DirectoryClient({ firms }: { firms: FirmDTO[] }) {
  const [filters, setFilters] = useState<FirmFilters>(DEFAULT_FILTERS);
  const [sortKey, setSortKey] = useState<SortKey>("rank");

  const challengeOptions = useMemo(
    () => uniqueSorted(firms.flatMap((f) => f.tags.map((t) => t.label))),
    [firms],
  );
  const platformOptions = useMemo(
    () => uniqueSorted(firms.flatMap((f) => f.platforms)),
    [firms],
  );

  const visible = useMemo(() => {
    const search = filters.search.trim().toLowerCase();

    const filtered = firms.filter((firm) => {
      if (search && !firm.name.toLowerCase().includes(search)) return false;

      if (
        filters.challenge &&
        !firm.tags.some((t) => t.label === filters.challenge)
      ) {
        return false;
      }

      if (
        filters.platform &&
        !firm.platforms.some((p) => p === filters.platform)
      ) {
        return false;
      }

      if (
        filters.minAccount > 0 &&
        (firm.maxAccount ?? 0) < filters.minAccount
      ) {
        return false;
      }

      if (
        filters.minDiscount > 0 &&
        (firm.topDiscount ?? 0) < filters.minDiscount
      ) {
        return false;
      }

      return true;
    });

    const sorted = [...filtered].sort((a, b) => {
      switch (sortKey) {
        case "rating":
          return (b.rating ?? 0) - (a.rating ?? 0);
        case "discount":
          return (b.topDiscount ?? 0) - (a.topDiscount ?? 0);
        case "rank":
        default:
          return (a.rank ?? 999) - (b.rank ?? 999);
      }
    });

    return sorted;
  }, [firms, filters, sortKey]);

  function handleSort(key: SortKey) {
    setSortKey(key);
  }

  return (
    <div className="space-y-4">
      <Filters
        filters={filters}
        onChange={setFilters}
        challengeOptions={challengeOptions}
        platformOptions={platformOptions}
      />

      <p className="font-mono text-xs text-muted" role="status" aria-live="polite">
        Showing {visible.length} of {firms.length} firms
      </p>

      {/* Table on >= sm, cards on mobile */}
      <div className="hidden sm:block">
        <FirmTable firms={visible} sortKey={sortKey} onSort={handleSort} />
      </div>
      <div className="space-y-3 sm:hidden">
        {visible.length === 0 ? (
          <div className="rounded-lg border border-panel-edge bg-panel p-8 text-center text-muted">
            No firms match your filters.
          </div>
        ) : (
          visible.map((firm) => <FirmCard key={firm.id} firm={firm} />)
        )}
      </div>
    </div>
  );
}
