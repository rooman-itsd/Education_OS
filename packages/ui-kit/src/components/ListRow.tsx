import type { ComponentType, CSSProperties, ReactNode } from "react";
import { ArrowRight } from "../icons";

export type RowTone = "accent" | "success" | "warning" | "danger" | "info" | "neutral";

const TONES: Record<RowTone, CSSProperties> = {
  accent: {},
  success: { "--row-bg": "var(--eos-success-tint)", "--row-fg": "var(--eos-success)" } as CSSProperties,
  warning: { "--row-bg": "var(--eos-warning-tint)", "--row-fg": "var(--eos-warning)" } as CSSProperties,
  danger: { "--row-bg": "var(--eos-danger-tint)", "--row-fg": "var(--eos-danger)" } as CSSProperties,
  info: { "--row-bg": "var(--eos-info-tint)", "--row-fg": "var(--eos-info)" } as CSSProperties,
  neutral: { "--row-bg": "var(--eos-surface-hover)", "--row-fg": "var(--eos-text-3)" } as CSSProperties,
};

export interface ListRowProps {
  title: ReactNode;
  meta?: ReactNode;
  /** Icon in a tinted tile on the left. */
  icon?: ComponentType<{ className?: string }>;
  /** Two-letter initials in a round tile instead of an icon. */
  initials?: string;
  /** A date tile instead of an icon: day number and short month. */
  date?: string;
  tone?: RowTone;
  /** Right-hand figure or badge. */
  trailing?: ReactNode;
  /** Makes the row a button (onClick) or a link (href), with an arrow. */
  onClick?: () => void;
  href?: string;
  /** Index for staggered reveals inside an `.eos-reveal` list. */
  index?: number;
}

/** One row of a list panel: tile, title and meta, trailing value, optional arrow. */
export function ListRow({ title, meta, icon: Icon, initials, date, tone = "accent", trailing, onClick, href, index }: ListRowProps) {
  const d = date ? new Date(`${date}T00:00:00`) : null;
  const inner = (
    <>
      {d ? (
        <span className="eos-row__date" aria-hidden>
          <b>{String(d.getDate()).padStart(2, "0")}</b>
          <span>{d.toLocaleDateString("en-GB", { month: "short" })}</span>
        </span>
      ) : Icon ? (
        <span className="eos-row__tile eos-pop-in" aria-hidden>
          <Icon />
        </span>
      ) : initials ? (
        <span className="eos-row__tile eos-row__tile--round eos-pop-in" aria-hidden>
          {initials}
        </span>
      ) : null}
      <span className="eos-row__text">
        <span className="eos-row__title">{title}</span>
        {meta && <span className="eos-row__meta">{meta}</span>}
      </span>
      {trailing && <span className="eos-row__value eos-slide-in">{trailing}</span>}
      {(onClick || href) && <ArrowRight className="eos-row__arrow" />}
    </>
  );
  const style = { ...TONES[tone], ...(index !== undefined ? ({ "--i": index } as CSSProperties) : {}) };
  if (href) {
    return (
      <li style={style}>
        <a className="eos-row" href={href}>
          {inner}
        </a>
      </li>
    );
  }
  if (onClick) {
    return (
      <li style={style}>
        <button type="button" className="eos-row" onClick={onClick}>
          {inner}
        </button>
      </li>
    );
  }
  return (
    <li style={style}>
      <div className="eos-row">{inner}</div>
    </li>
  );
}

/** The list that holds rows. `divided` draws hairlines between rows instead of hover tints. */
export function List({ divided = false, reveal = false, inView = true, label, children }: { divided?: boolean; reveal?: boolean; inView?: boolean; label?: string; children: ReactNode }) {
  const cls = ["eos-list", divided ? "eos-list--divided" : "", reveal ? "eos-reveal" : "", reveal && inView ? "is-in" : ""].filter(Boolean).join(" ");
  return (
    <ul className={cls} aria-label={label}>
      {children}
    </ul>
  );
}
