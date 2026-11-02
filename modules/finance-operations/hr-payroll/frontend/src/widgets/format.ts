import type { LeaveRequest, Money, PayrollRunStatus } from "../api/client";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });

/** The contract's Money pattern: optional minus, rupees, up to two decimals of paise. */
const MONEY = /^(-?)(\d+)(?:\.(\d{1,2}))?$/;

/**
 * Whole paise of a Money decimal string, exactly ("1500.5" -> 150050), so the amount never goes through
 * floating point before display. 0 when the value is missing or not a Money string.
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

function calendarDate(date: string | null | undefined): Date | null {
  if (!date) return null;
  const d = new Date(`${date}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  const d = calendarDate(date);
  if (!d) return date || "—";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Two contract dates as one range: "5 Nov 2026" for one day, "5 Nov – 7 Nov 2026" within a year, else both in full. */
export function dateRange(from: string, to: string): string {
  if (!to || from === to) return day(from);
  const a = calendarDate(from);
  const b = calendarDate(to);
  if (a && b && a.getFullYear() === b.getFullYear()) {
    return `${a.toLocaleDateString("en-IN", { day: "numeric", month: "short" })} – ${day(to)}`;
  }
  return `${day(from)} – ${day(to)}`;
}

/** A contract month (YYYY-MM) as "October 2026". */
export function month(period: string | null | undefined): string {
  const d = calendarDate(period ? `${period}-01` : null);
  if (!d) return period || "—";
  return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

/** Today's month (YYYY-MM) in India: the contract judges "current" on the Indian date (Asia/Kolkata). */
export function indianMonth(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit" }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}`;
}

/** Leave days, which come in halves: "Half day", "1 day", "2.5 days". */
export function leaveDays(days: number | null | undefined): string {
  if (days == null || Number.isNaN(days)) return "—";
  if (days === 0.5) return "Half day";
  return `${days} ${days === 1 ? "day" : "days"}`;
}

/** The dates of a leave request, with the half when it is half a day. */
export function leaveDates(r: Pick<LeaveRequest, "from" | "to" | "half_day">): string {
  const range = dateRange(r.from, r.to);
  if (r.half_day === "first_half") return `${range} (first half)`;
  if (r.half_day === "second_half") return `${range} (second half)`;
  return range;
}

/** Words for a payroll run status (contracts/openapi.yaml, PayrollRun.status). */
export const RUN_STATUS_LABEL: Record<PayrollRunStatus, string> = {
  computing: "Computing",
  review: "In review",
  submitted: "Awaiting approval",
  approved: "Approved",
  paid: "Paid",
  failed: "Failed",
};
