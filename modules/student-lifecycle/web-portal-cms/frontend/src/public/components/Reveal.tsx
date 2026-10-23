import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ElementType,
  type HTMLAttributes,
  type ReactNode,
  type RefObject,
} from "react";
import { prefersReducedMotion } from "@eos/ui-kit";

type RevealState = "visible" | "waiting" | "in";

/**
 * Scroll-reveal helpers. Content is visible by default: a block is only hidden ("waiting") once script
 * has confirmed it starts below the screen, and it reveals as soon as any part of it scrolls into
 * view (threshold 0), so neither a failed script nor a section taller than the viewport can leave it
 * hidden. Reduced motion, or no IntersectionObserver, keeps everything visible with no entrance.
 * CSS: `.wpc-rv` / `.wpc-rvg` in public.css.
 */
export function useReveal(ref: RefObject<Element>): RevealState {
  const [state, setState] = useState<RevealState>("visible");

  // Before the first paint: hold back only what is genuinely below the fold.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined" || prefersReducedMotion()) return;
    if (el.getBoundingClientRect().top > window.innerHeight) setState("waiting");
  }, [ref]);

  useEffect(() => {
    const el = ref.current;
    if (state !== "waiting" || !el) return;
    let frame = 0;
    const reveal = () => {
      setState("in");
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting || e.boundingClientRect.top < 0)) reveal();
      },
      { threshold: 0, rootMargin: "0px 0px -6% 0px" },
    );
    // The observer only reports crossings, so a jump that carries a short block from below the
    // screen to above it in one step (an in-page link, End, a fast fling) would never reveal it.
    // A once-per-frame check of its top catches that case.
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (el.getBoundingClientRect().top < window.innerHeight * 0.94) reveal();
      });
    };
    io.observe(el);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [ref, state]);

  return state;
}

const stateClass = (state: RevealState) => (state === "waiting" ? "is-waiting" : state === "in" ? "is-in" : "");

/** Other attributes (id, aria-*) pass through, so a heading or section can be the reveal itself. */
type PassThrough = Omit<HTMLAttributes<HTMLElement>, "className" | "children" | "style">;

/** Fades a single block up as it enters the viewport. */
export function Reveal({
  children,
  className,
  delay = 0,
  as,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: ElementType;
} & PassThrough) {
  const ref = useRef<HTMLElement>(null);
  const state = useReveal(ref);
  const Tag = as ?? "div";
  return (
    <Tag
      {...rest}
      ref={ref}
      className={["wpc-rv", stateClass(state), className].filter(Boolean).join(" ")}
      style={delay ? ({ "--rv-delay": `${delay}ms` } as CSSProperties) : undefined}
    >
      {children}
    </Tag>
  );
}

/**
 * A container whose direct children fade up in turn as it enters the viewport. Give each child
 * `style={stagger(index)}`. Renders a `<div>` by default; pass `as="ul"` / `as="ol"` for a semantic list.
 */
export function RevealGroup({
  children,
  className,
  as,
  ariaLabel,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: ElementType;
  ariaLabel?: string;
} & PassThrough) {
  const ref = useRef<HTMLElement>(null);
  const state = useReveal(ref);
  const Tag = as ?? "div";
  return (
    <Tag
      {...rest}
      ref={ref}
      aria-label={ariaLabel}
      className={["wpc-rvg", stateClass(state), className].filter(Boolean).join(" ")}
    >
      {children}
    </Tag>
  );
}

/** Inline style carrying the stagger index for a `RevealGroup` child. */
export const stagger = (index: number): CSSProperties => ({ ["--i" as string]: index }) as CSSProperties;
