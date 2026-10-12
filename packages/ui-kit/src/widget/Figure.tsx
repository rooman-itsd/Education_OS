import type { ReactNode } from "react";
import { StatCard, type Stat } from "../components/StatCard";

/**
 * The body of a `figure` widget. A figure widget's component returns this; the shell gathers
 * every figure into the stat strip at the top of the dashboard.
 */
export function Figure(props: Stat) {
  return <StatCard {...props} />;
}

/** The strip of figures at the top of a dashboard. */
export function FigureStrip({ children, label = "Key figures" }: { children: ReactNode; label?: string }) {
  return (
    <section className="eos-stat-grid" aria-label={label}>
      {children}
    </section>
  );
}
