import type { CSSProperties, ReactNode } from "react";
import { AlertTriangle, Search } from "../icons";

/** Nothing to show, with a word on why and what to do next. */
export function EmptyState({ title, children, icon, action }: { title?: ReactNode; children?: ReactNode; icon?: ReactNode; action?: ReactNode }) {
  return (
    <div className="eos-empty">
      <span className="eos-empty__icon" aria-hidden>
        {icon ?? <Search />}
      </span>
      {title && <span className="eos-empty__title">{title}</span>}
      {children && <span>{children}</span>}
      {action}
    </div>
  );
}

/** Something went wrong, with a way to retry. */
export function ErrorState({ title = "Could not load", children, onRetry }: { title?: ReactNode; children?: ReactNode; onRetry?: () => void }) {
  return (
    <div className="eos-empty eos-empty--error" role="alert">
      <span className="eos-empty__icon" aria-hidden>
        <AlertTriangle />
      </span>
      <span className="eos-empty__title">{title}</span>
      {children && <span>{children}</span>}
      {onRetry && (
        <button type="button" className="eos-btn eos-btn--secondary eos-btn--sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/** A shimmering placeholder the size of the content that will replace it. */
export function Skeleton({ width = "100%", height = 14, radius, style }: { width?: string | number; height?: string | number; radius?: number; style?: CSSProperties }) {
  return <span className="eos-skeleton" aria-hidden style={{ width, height, borderRadius: radius, ...style }} />;
}

/** Several skeleton lines, for a loading list or table. */
export function SkeletonLines({ lines = 3 }: { lines?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={`${100 - (i % 3) * 18}%`} />
      ))}
    </div>
  );
}
