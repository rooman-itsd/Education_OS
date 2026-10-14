import { useRef, type CSSProperties, type ElementType, type ReactNode } from "react";
import { useInView } from "@eos/ui-kit";

/**
 * Scroll-reveal helpers built on the ui-kit's existing entrance primitives — no animation library,
 * transform/opacity only, and reduced-motion safe (the kit's global `prefers-reduced-motion` rule
 * forces the final state, and `useInView` returns true immediately when motion is reduced or there is
 * no IntersectionObserver).
 */

/** Fades a single block up as it enters the viewport (ui-kit `.eos-enter`). */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref);
  return (
    <div
      ref={ref}
      className={["eos-enter", inView ? "is-in" : "", className].filter(Boolean).join(" ")}
      style={delay ? ({ "--enter-delay": `${delay}ms` } as CSSProperties) : undefined}
    >
      {children}
    </div>
  );
}

/**
 * A container whose direct children fade up in turn as the container enters the viewport (ui-kit
 * `.eos-reveal`). Give each child `style={{ "--i": index }}` for the stagger (the `stagger()` helper
 * below). Renders a `<div>` by default; pass `as="ul"` to keep a semantic list (e.g. a chip group) with
 * the same reveal behaviour.
 */
export function RevealGroup({
  children,
  className,
  as,
  ariaLabel,
}: {
  children: ReactNode;
  className?: string;
  as?: ElementType;
  ariaLabel?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const Tag = as ?? "div";
  return (
    <Tag
      ref={ref}
      aria-label={ariaLabel}
      className={["eos-reveal", inView ? "is-in" : "", className].filter(Boolean).join(" ")}
    >
      {children}
    </Tag>
  );
}

/** Inline style carrying the stagger index for a `RevealGroup` child. */
export const stagger = (index: number): CSSProperties => ({ ["--i" as string]: index }) as CSSProperties;
