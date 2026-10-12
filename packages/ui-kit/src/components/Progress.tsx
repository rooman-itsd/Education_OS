import { useRef, type CSSProperties, type ReactNode } from "react";
import { useInView } from "../motion";
import { CountUp } from "./CountUp";

/** A single progress bar. `value` is 0 to 100. */
export function ProgressBar({ value, color, label, animate = true }: { value: number; color?: string; label?: string; animate?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, 0.2);
  const pct = Math.max(0, Math.min(100, value));
  return (
    <span ref={ref} className="eos-progress" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <span
        className={animate ? "eos-progress__fill eos-fill" : "eos-progress__fill"}
        style={{ width: animate && !inView ? 0 : `${pct}%`, ...(color ? { backgroundImage: `linear-gradient(90deg, ${color}99, ${color})` } : {}) }}
      />
    </span>
  );
}

export interface ProgressItem {
  label: ReactNode;
  count: number;
  /** Bar colour for this row; defaults to the page accent. */
  color?: string;
}

/**
 * Horizontal bars, each relative to the largest item (or the first, for a funnel). Numbers count
 * up and bars fill once the list scrolls into view.
 */
export function ProgressList({ items, relativeToFirst = false, unit = "", showShare = relativeToFirst }: { items: ProgressItem[]; relativeToFirst?: boolean; unit?: string; showShare?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, 0.2);
  const max = relativeToFirst ? items[0]?.count || 1 : Math.max(1, ...items.map((i) => i.count));
  return (
    <div ref={ref} className="eos-progress-list">
      {items.map((it, i) => {
        const pct = Math.round((it.count / max) * 1000) / 10;
        const delay = 250 + i * 160;
        return (
          <div key={i} className="eos-progress-list__row">
            <div className="eos-progress-list__head">
              <span className="eos-progress-list__label">
                {it.color && <span className="eos-progress-list__dot" style={{ background: it.color }} aria-hidden />}
                {it.label}
              </span>
              <span className="eos-progress-list__value">
                <CountUp end={it.count} active={inView} duration={1000} delay={delay} />
                {unit}
                {showShare && (
                  <span className="eos-progress-list__pct" style={{ opacity: inView ? 1 : 0, transition: `opacity 400ms ease ${delay + 300}ms` }}>
                    {pct}%
                  </span>
                )}
              </span>
            </div>
            <span className="eos-progress">
              <span
                className={`eos-progress__fill eos-fill eos-sheen ${inView ? "is-in" : ""}`}
                style={{ width: inView ? `${pct}%` : 0, transitionDelay: `${delay}ms`, "--sheen-delay": `${delay + 900}ms`, ...(it.color ? { backgroundImage: `linear-gradient(90deg, ${it.color}99, ${it.color})` } : {}) } as CSSProperties}
              />
            </span>
          </div>
        );
      })}
    </div>
  );
}
