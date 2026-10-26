import type { Money, PaymentMode } from "../api/client";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });

/**
 * Display value of a Money decimal string, in Indian rupees ("1500.00" -> "₹1,500.00").
 * Number() is used for display only; amounts are never added up here.
 */
export function rupees(amount: Money | null | undefined): string {
  const n = Number(amount);
  if (amount == null || amount === "" || !Number.isFinite(n)) return "—";
  return INR.format(n);
}

/** Number value of a Money string for comparisons and bar widths; 0 when it is not a number. */
export function amount(value: Money | null | undefined): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

/** Whole-number percent of part in whole; 0 when the whole is 0. */
export function percent(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** A target period (YYYY-MM) as "Apr 2026". */
export function month(period: string): string {
  const d = new Date(`${period}-01T00:00:00`);
  if (Number.isNaN(d.getTime())) return period;
  return d.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

export const MODE_LABEL: Record<PaymentMode, string> = {
  online: "Online",
  cash: "Cash",
  cheque: "Cheque",
  demand_draft: "Demand draft",
  bank_transfer: "Bank transfer",
};
