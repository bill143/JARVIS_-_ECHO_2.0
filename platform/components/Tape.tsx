// The "trading-tape" stat ribbon. Shows top-line stats in a mono ticker style.

type TapeStat = { label: string; value: string };

export function Tape({ stats }: { stats: TapeStat[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-panel-edge bg-panel">
      <ul className="flex flex-wrap divide-y divide-line sm:divide-y-0">
        {stats.map((s, i) => (
          <li
            key={s.label}
            className={`flex min-w-[50%] flex-1 flex-col gap-1 px-4 py-3 sm:min-w-0 ${
              i > 0 ? "sm:border-l sm:border-line" : ""
            }`}
          >
            <span className="font-mono text-[11px] uppercase tracking-widest text-muted">
              {s.label}
            </span>
            <span className="font-mono text-lg font-semibold text-accent">
              {s.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
