// Small formatting helpers shared across components.

export function formatMoney(value: number): string {
  if (value >= 1000 && value % 1000 === 0) {
    return `$${value / 1000}k`;
  }
  return `$${value.toLocaleString("en-US")}`;
}

export function formatAccountRange(
  min: number | null,
  max: number | null,
): string {
  if (min == null || max == null) return "—";
  if (min === max) return formatMoney(min);
  return `${formatMoney(min)}–${formatMoney(max)}`;
}

export function formatDiscount(percent: number | null): string {
  return percent != null ? `${percent}%` : "—";
}

export function formatDate(iso: string | null): string {
  if (!iso) return "No expiry";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
