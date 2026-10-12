import { forwardRef, type CSSProperties, type HTMLAttributes, type ReactNode } from "react";
import { ArrowRight } from "../icons";

export interface PanelProps extends HTMLAttributes<HTMLElement> {
  /** Lift on hover. On by default; off for panels that are mostly text. */
  lift?: boolean;
  children?: ReactNode;
}

/** The white bordered box most dashboard content lives in. */
export const Panel = forwardRef<HTMLElement, PanelProps>(function Panel({ lift = true, className = "", children, ...rest }, ref) {
  return (
    <section ref={ref} className={["eos-panel", lift ? "eos-lift" : "", className].filter(Boolean).join(" ")} {...rest}>
      {children}
    </section>
  );
});

export interface PanelHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  /** A link, a segmented control or a button, top right. */
  action?: ReactNode;
  /** Icon chip before the title. */
  icon?: ReactNode;
  /** The heading level; h2 inside a page, h3 inside a widget. */
  as?: "h2" | "h3";
  id?: string;
}

export function PanelHeader({ title, subtitle, action, icon, as: Heading = "h2", id }: PanelHeaderProps) {
  return (
    <div className="eos-panel__header">
      <div style={{ minWidth: 0 }}>
        <Heading className="eos-panel__title" id={id}>
          {icon && <span className="eos-chip" aria-hidden>{icon}</span>}
          {title}
        </Heading>
        {subtitle && <p className="eos-panel__subtitle">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PanelBody({ flush = false, children, style }: { flush?: boolean; children?: ReactNode; style?: CSSProperties }) {
  return (
    <div className={flush ? "eos-panel__body eos-panel__body--flush" : "eos-panel__body"} style={style}>
      {children}
    </div>
  );
}

export function PanelFooter({ label, value, children }: { label?: ReactNode; value?: ReactNode; children?: ReactNode }) {
  return (
    <div className="eos-panel__footer">
      {children ?? (
        <>
          <span>{label}</span>
          <b>{value}</b>
        </>
      )}
    </div>
  );
}

/** A small text link for panel headers, e.g. "View all". */
export function PanelLink({ onClick, href, children }: { onClick?: () => void; href?: string; children: ReactNode }) {
  if (href) {
    return (
      <a className="eos-panel-link" href={href}>
        {children}
        <ArrowRight />
      </a>
    );
  }
  return (
    <button type="button" className="eos-panel-link" onClick={onClick}>
      {children}
      <ArrowRight />
    </button>
  );
}
