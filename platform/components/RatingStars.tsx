// Accessible star rating. Renders an aria-label with the numeric value and a
// visual row of full/half/empty stars built from the accent token.

export function RatingStars({
  rating,
  showValue = true,
}: {
  rating: number | null;
  showValue?: boolean;
}) {
  if (rating == null) {
    return <span className="text-muted">Unrated</span>;
  }

  const rounded = Math.round(rating * 2) / 2;
  const stars = Array.from({ length: 5 }, (_, i) => {
    const position = i + 1;
    if (rounded >= position) return "full";
    if (rounded + 0.5 === position) return "half";
    return "empty";
  });

  return (
    <span
      className="inline-flex items-center gap-1"
      role="img"
      aria-label={`Rated ${rating} out of 5`}
    >
      <span aria-hidden="true" className="inline-flex">
        {stars.map((s, i) => (
          <span
            key={i}
            className={
              s === "empty" ? "text-panel-edge" : "text-amber"
            }
          >
            {s === "half" ? "⯪" : "★"}
          </span>
        ))}
      </span>
      {showValue && (
        <span className="font-mono text-sm text-text">{rating.toFixed(1)}</span>
      )}
    </span>
  );
}
