import type { Money, PurchaseOrderStatus } from "../api/client";

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

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Words for a purchase order status (contracts/openapi.yaml, PurchaseOrderStatus). */
export const STATUS_LABEL: Record<PurchaseOrderStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  returned: "Returned",
  issued: "Issued",
  partially_received: "Partly received",
  received: "Received",
  closed: "Closed",
  cancelled: "Cancelled",
};
