import type { BadgeTone } from "@eos/ui-kit";
import type { TournamentLevel } from "../api/client";

const DATE: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" };
const TIME: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hourCycle: "h23" };

/** A contract date (YYYY-MM-DD) as "5 Nov 2026", read as a local calendar date. */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", DATE);
}

/** A contract date-time as the local calendar day, "5 Nov 2026". */
export function dayOf(instant: string): string {
  const d = new Date(instant);
  if (Number.isNaN(d.getTime())) return instant;
  return d.toLocaleDateString("en-IN", DATE);
}

/** A contract date-time as the local day and time, "5 Nov 2026, 09:30". */
export function dateTime(instant: string): string {
  const d = new Date(instant);
  if (Number.isNaN(d.getTime())) return instant;
  return `${d.toLocaleDateString("en-IN", DATE)}, ${d.toLocaleTimeString("en-IN", TIME)}`;
}

/** A date as YYYY-MM-DD in local time. */
function iso(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Today as YYYY-MM-DD in local time, and that date plus some days. */
export function isoDay(offsetDays = 0, now = new Date()): string {
  return iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() + offsetDays));
}

/** The local calendar day (YYYY-MM-DD) of a contract date-time, for the row's date tile. */
export function isoDayOf(instant: string): string | undefined {
  const d = new Date(instant);
  return Number.isNaN(d.getTime()) ? undefined : iso(d);
}

/** "5 Nov 2026" for one day, "5 Nov 2026 – 7 Nov 2026" for several. */
export function dayRange(start: string, end: string): string {
  return start === end ? day(start) : `${day(start)} – ${day(end)}`;
}

/**
 * The days a calendar tournament covers. Its `ends_at` is the local start of the day after its last day, so the
 * last day is the one just before it.
 */
export function calendarDays(startsAt: string, endsAt?: string): string {
  const first = dayOf(startsAt);
  if (!endsAt) return first;
  const end = new Date(endsAt);
  if (Number.isNaN(end.getTime())) return first;
  const last = dayOf(new Date(end.getTime() - 1).toISOString());
  return last === first ? first : `${first} – ${last}`;
}

export const LEVEL: Record<TournamentLevel, string> = {
  intra_institution: "Intra-institution",
  inter_university: "Inter-university",
  state: "State",
  national: "National",
  international: "International",
};

/** Badge of the athlete's own entries in a tournament. */
export const ENTERED: Record<"confirmed" | "pending", { label: string; tone: BadgeTone }> = {
  confirmed: { label: "Entered", tone: "success" },
  pending: { label: "Entry pending", tone: "warning" },
};

/** "1 tournament", "3 tournaments". */
export const tournaments = (n: number) => (n === 1 ? "1 tournament" : `${n} tournaments`);

/** "1 item", "3 items": calendar rows, tournaments and fixtures together. */
export const items = (n: number) => (n === 1 ? "1 item" : `${n} items`);
