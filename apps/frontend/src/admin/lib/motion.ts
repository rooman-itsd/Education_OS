// Small motion helpers for the admin screens: start an animation when its element scrolls into
// view, and honour prefers-reduced-motion (final state at once).

import { useEffect, useState, type RefObject } from 'react';

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

/** True once the element has been at least `threshold` visible. True at once without IntersectionObserver or with reduced motion. */
export function useInView(ref: RefObject<Element>, threshold = 0.45, delayMs = 120): boolean {
  // Reduced motion: no entrance to wait for, so everything is in its final state at once.
  const [inView, setInView] = useState(() => typeof IntersectionObserver === 'undefined' || prefersReducedMotion());
  useEffect(() => {
    const el = ref.current;
    if (inView || !el) return;
    let timer = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          timer = window.setTimeout(() => setInView(true), delayMs);
        }
      },
      { threshold }
    );
    io.observe(el);
    return () => {
      io.disconnect();
      window.clearTimeout(timer);
    };
  }, [ref, inView, threshold, delayMs]);
  return inView;
}

/** Ease-out cubic: quick start, gentle settle, no overshoot. */
export const easeOut = (k: number) => 1 - Math.pow(1 - k, 3);

/** Milliseconds since `active` became true, ticking until `total`; `total` at once with reduced motion. */
export function useElapsed(active: boolean, total: number): number {
  const reduced = prefersReducedMotion();
  const [t, setT] = useState(reduced ? total : 0);
  useEffect(() => {
    if (!active || reduced) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const e = Math.min(total, now - start);
      setT(e);
      if (e < total) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, total, reduced]);
  return t;
}
