import type { Priority } from "../api/client";

const DAY: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" };

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", DAY);
}

/**
 * The Indian calendar date of a contract date-time, as "30 Oct 2026". Business dates in e-office are dates in
 * Asia/Kolkata (contracts/openapi.yaml), so a file received at 20:00 UTC counts from the next day, whatever the
 * viewer's time zone. "—" when it is missing or unreadable.
 */
export function indianDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", { ...DAY, timeZone: "Asia/Kolkata" });
}

/** Words for a file's priority (contracts/openapi.yaml, Priority). */
export const PRIORITY_LABEL: Record<Priority, string> = {
  normal: "Normal",
  urgent: "Urgent",
  immediate: "Immediate",
};

/** "for approval" -> "For approval": the sender's words, with a capital first letter. */
export function sentence(text: string | null | undefined): string | null {
  const t = text?.trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : null;
}
