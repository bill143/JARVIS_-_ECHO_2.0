// Highlights a firm's best discount. Falls back to a note (e.g. "120% refund")
// when there is no numeric percent.

export function DiscountBadge({
  percent,
  note,
}: {
  percent: number | null;
  note?: string | null;
}) {
  if (percent == null && !note) {
    return <span className="font-mono text-sm text-muted">No active offer</span>;
  }

  const label = percent != null ? `${percent}% OFF` : note;

  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-accent bg-panel px-2 py-1 font-mono text-xs font-semibold uppercase tracking-wide text-accent">
      {label}
    </span>
  );
}
