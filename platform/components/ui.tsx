import Link from "next/link";
import type { ReactNode, AnchorHTMLAttributes } from "react";

// Small shared primitives: Button, Tag, Section.

type ButtonVariant = "primary" | "ghost";

type ButtonProps = {
  href: string;
  variant?: ButtonVariant;
  external?: boolean;
  children: ReactNode;
  className?: string;
} & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "children">;

const buttonBase =
  "inline-flex items-center justify-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none";

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-bg hover:opacity-90 font-semibold",
  ghost:
    "border border-panel-edge bg-panel text-text hover:border-accent",
};

export function Button({
  href,
  variant = "primary",
  external = false,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  const cls = `${buttonBase} ${buttonVariants[variant]} ${className}`;
  if (external) {
    return (
      <a
        href={href}
        className={cls}
        rel="nofollow sponsored noopener"
        target="_blank"
        {...rest}
      >
        {children}
      </a>
    );
  }
  return (
    <Link href={href} className={cls} {...rest}>
      {children}
    </Link>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded border border-panel-edge bg-bg px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide text-muted">
      {children}
    </span>
  );
}

export function Section({
  title,
  eyebrow,
  children,
  className = "",
}: {
  title?: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`mb-10 ${className}`}>
      {eyebrow && (
        <p className="mb-1 font-mono text-xs uppercase tracking-widest text-accent">
          {eyebrow}
        </p>
      )}
      {title && (
        <h2 className="mb-4 text-xl font-bold text-text sm:text-2xl">{title}</h2>
      )}
      {children}
    </section>
  );
}
