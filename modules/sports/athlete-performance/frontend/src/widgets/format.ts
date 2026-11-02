import type { BadgeTone } from "@eos/ui-kit";
import type { ClearanceStatus, Metric, Trend } from "../api/client";

const NUMBER = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** A measured value with its metric's unit: "11.24 s", "12.5%", "62 kg"; "—" when there is none. */
export function measure(value: number | null | undefined, unit?: string): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const n = NUMBER.format(value);
  if (!unit) return n;
  return unit === "%" ? `${n}%` : `${n} ${unit}`;
}

/** A metric's name, or its short id while the catalogue does not have it (beyond the first page, or removed). */
export function metricName(metric: Metric | undefined, id: string): string {
  return metric?.name ?? `Metric ${id.slice(0, 8)}`;
}

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** A contract date-time as the local calendar day, "5 Nov 2026". */
export function dayOf(instant: string): string {
  const d = new Date(instant);
  if (Number.isNaN(d.getTime())) return instant;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Today as YYYY-MM-DD in local time, and that date plus some days. */
export function isoDay(offsetDays = 0, now = new Date()): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Two-letter initials of a name, for the round tile of a row. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0]![0]! + parts[parts.length - 1]![0]! : (parts[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}

export const CLEARANCE: Record<ClearanceStatus, { label: string; tone: BadgeTone }> = {
  cleared: { label: "Cleared", tone: "success" },
  restricted: { label: "Restricted", tone: "warning" },
  not_cleared: { label: "Not cleared", tone: "danger" },
};

export const TREND: Record<Trend, { label: string; tone: BadgeTone; arrow: string }> = {
  improving: { label: "Improving", tone: "success", arrow: "↑" },
  steady: { label: "Steady", tone: "neutral", arrow: "→" },
  declining: { label: "Declining", tone: "warning", arrow: "↓" },
  no_data: { label: "Not enough data", tone: "neutral", arrow: "" },
};

/** "1 athlete", "3 athletes". */
export const athletes = (n: number) => (n === 1 ? "1 athlete" : `${n} athletes`);
