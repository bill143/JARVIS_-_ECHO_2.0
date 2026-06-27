import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-8">
      {eyebrow && (
        <p className="mb-2 font-mono text-xs uppercase tracking-widest text-accent">
          {eyebrow}
        </p>
      )}
      <h1 className="mb-2 text-3xl font-bold tracking-tight text-text">
        {title}
      </h1>
      {children && <div className="max-w-2xl text-muted">{children}</div>}
    </header>
  );
}
