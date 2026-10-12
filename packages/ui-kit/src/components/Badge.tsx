import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "accent";

/** A status label. Always carries a word, never colour alone. */
export function Badge({ tone = "neutral", dot = false, children }: { tone?: BadgeTone; dot?: boolean; children: ReactNode }) {
  return <span className={["eos-badge", tone === "neutral" ? "" : `eos-badge--${tone}`, dot ? "eos-badge--dot" : ""].filter(Boolean).join(" ")}>{children}</span>;
}
