import type { InvestigatorRole, Money } from "../api/client";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });

/** The contract's Money pattern: optional minus, rupees, up to two decimals of paise. */
const MONEY = /^(-?)(\d+)(?:\.(\d{1,2}))?$/;

/**
 * Whole paise of a Money decimal string, exactly ("1500.5" -> 150050), so sums, differences and threshold
 * checks never go through floating point. 0 when the value is missing or not a Money string.
 */
export function paise(value: Money | null | undefined): number {
  const m = MONEY.exec(value ?? "");
  if (!m) return 0;
  const p = Number(m[2]) * 100 + Number((m[3] ?? "").padEnd(2, "0"));
  return m[1] ? -p : p;
}

/** Display value of a Money decimal string, in Indian rupees ("1500.00" -> "₹1,500.00"). */
export function rupees(amount: Money | null | undefined): string {
  if (amount == null || !MONEY.test(amount)) return "—";
  return INR.format(paise(amount) / 100);
}

/** Display value of an amount already in whole paise (a sum or difference worked out with paise()). */
export function rupeesFromPaise(p: number): string {
  return INR.format(p / 100);
}

/**
 * Whole-number percent of used in allocated, rounded down so the figure never reads 80% or 100% before the
 * threshold is actually reached. null when nothing is allocated.
 */
export function usedPercent(used: number, allocated: number): number | null {
  return allocated > 0 ? Math.floor((used * 100) / allocated) : null;
}

/** How close spend is to the allocation: the 80% and 100% thresholds of the product rules. */
export type Level = "ok" | "warning" | "danger";

/** Level of used (committed plus spent) against allocated, compared exactly in paise. */
export function level(used: number, allocated: number): Level {
  if (allocated <= 0) return used > 0 ? "danger" : "ok";
  if (used * 100 >= allocated * 100) return "danger";
  if (used * 100 >= allocated * 80) return "warning";
  return "ok";
}

/** Words for a level, for the badge (never colour alone). null when there is nothing to flag. */
export function levelLabel(lvl: Level, used: number, allocated: number): string | null {
  if (lvl === "danger") return used > allocated ? "Over budget" : "Fully used";
  if (lvl === "warning") return "Nearing limit";
  return null;
}

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Today's local calendar date as YYYY-MM-DD, to compare with contract dates. */
export function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Whole days from today to a contract date (negative when it has passed). */
export function daysUntil(date: string): number {
  const from = new Date(`${today()}T00:00:00`).getTime();
  const to = new Date(`${date}T00:00:00`).getTime();
  return Math.round((to - from) / 86_400_000);
}

export const ROLE_LABEL: Record<InvestigatorRole, string> = {
  principal: "Principal investigator",
  co_investigator: "Co-investigator",
};
