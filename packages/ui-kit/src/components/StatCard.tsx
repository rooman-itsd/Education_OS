import type { ComponentType, CSSProperties, ReactNode } from "react";
import { CountUp } from "./CountUp";

export type StatTone = "up" | "alert" | "muted";
export type ChipTone = "accent" | "success" | "warning" | "danger" | "info";

export interface Stat {
  label: string;
  /** A number counts up; anything else is shown as given. */
  value: number | ReactNode;
  /** Formatting for a numeric value. */
  decimals?: number;
  prefix?: string;
  suffix?: string;
  icon?: ComponentType<{ className?: string }>;
  /** Small figure under the value, e.g. "+4.8%" or "12 urgent". */
  delta?: ReactNode;
  deltaTone?: StatTone;
  /** Supporting text after the delta, e.g. "vs last term". */
  note?: ReactNode;
  /** Icon chip colour; defaults from position and delta tone. */
  chip?: ChipTone;
  /** Makes the card a link to the page behind the number. */
  href?: string;
  /** Small indicator at the bottom right (sparkline, ring, bar), 96 x 30. */
  viz?: ReactNode;
}

const chipFor = (index: number, tone: StatTone): ChipTone => (index === 0 ? "accent" : tone === "alert" ? "warning" : tone === "up" ? "success" : "accent");

/**
 * A key figure: white card, light border, a tinted icon chip, the figure counting up and its
 * change below. Status colour is kept for the delta line so the card itself stays calm.
 */
export function StatCard({ label, value, decimals, prefix, suffix, icon: Icon, delta, deltaTone = "up", note, chip, href, viz, index = 0 }: Stat & { index?: number }) {
  const style = { animationDelay: `${index * 60}ms` } as CSSProperties;
  const body = (
    <>
      <div className="eos-stat__top">
        <span className="eos-stat__label">{label}</span>
        {Icon && (
          <span className={`eos-chip eos-chip--${chip ?? chipFor(index, deltaTone)}`} aria-hidden>
            <Icon />
          </span>
        )}
      </div>
      <div className="eos-stat__bottom">
        <div style={{ minWidth: 0 }}>
          <div className="eos-stat__value">{typeof value === "number" ? <CountUp end={value} decimals={decimals} prefix={prefix} suffix={suffix} /> : value}</div>
          {(delta || note) && (
            <div className={`eos-stat__delta eos-stat__delta--${deltaTone}`}>
              {delta && <b>{delta}</b>}
              {delta && note && " · "}
              {note}
            </div>
          )}
        </div>
        {viz && <div className="eos-stat__viz">{viz}</div>}
      </div>
    </>
  );
  return href ? (
    <a className="eos-stat" href={href} style={style}>
      {body}
    </a>
  ) : (
    <div className="eos-stat" style={style}>
      {body}
    </div>
  );
}

/** A row of stat cards; wraps to two then one column on narrow screens. */
export function StatGrid({ stats, label = "Key figures" }: { stats: Stat[]; label?: string }) {
  return (
    <section className="eos-stat-grid" aria-label={label}>
      {stats.map((s, i) => (
        <StatCard key={s.label} index={i} {...s} />
      ))}
    </section>
  );
}
