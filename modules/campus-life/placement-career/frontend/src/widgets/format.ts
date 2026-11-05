import type { ApplicationStatus, Money } from "../api/client";

const INDIA = "Asia/Kolkata";
const DAY: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric", timeZone: INDIA };

/**
 * A contract date (YYYY-MM-DD) as "5 Nov 2026". Business dates in placement-career are Indian calendar dates
 * (contracts/openapi.yaml), so the date is read as midnight in India and shown in Asia/Kolkata: the same day whatever
 * the viewer's time zone. "—" when missing; the raw text when it is not a date.
 */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00+05:30`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", DAY);
}

const WHOLE_RUPEES = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const RUPEES_AND_PAISE = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * A Money string as Indian rupees with Indian digit grouping: "650000" → "₹6,50,000", "650000.5" → "₹6,50,000.50".
 * Null when missing or unreadable.
 */
export function rupees(amount: Money | null | undefined): string | null {
  if (amount === null || amount === undefined || amount.trim() === "") return null;
  const n = Number(amount);
  if (!Number.isFinite(n)) return null;
  return (Number.isInteger(n) ? WHOLE_RUPEES : RUPEES_AND_PAISE).format(n);
}

/** Words for an application status, as the student and the officer see it. */
export const STATUS_LABEL: Record<ApplicationStatus, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  in_process: "In process",
  offered: "Offer made",
  accepted: "Offer accepted",
  declined: "Offer declined",
  rejected: "Not selected",
  withdrawn: "Withdrawn",
};

/** "1 opening", "3 openings". */
export function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The sum of a count-by-status object, ignoring missing or non-numeric values. */
export function total(counts: Partial<Record<string, number>> | null | undefined): number {
  return Object.values(counts ?? {}).reduce<number>((sum, v) => sum + (typeof v === "number" ? v : 0), 0);
}
