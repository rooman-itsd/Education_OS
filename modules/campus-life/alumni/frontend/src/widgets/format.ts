import type { MySession, SessionMode } from "../api/client";

const ZONE = "Asia/Kolkata";

/** A contract date (YYYY-MM-DD, already an Asia/Kolkata calendar date) as "5 Nov 2026". */
export function day(date: string | null | undefined): string {
  if (!date) return "—";
  const d = new Date(`${date}T00:00:00`);
  if (Number.isNaN(d.getTime())) return date;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function instant(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * A contract date-time (UTC) as the time in India, whatever the viewer's zone: "Thu, 5 Nov 2026, 4:30 pm".
 * "—" when it is missing or unreadable.
 */
export function indianDateTime(iso: string | null | undefined): string {
  const d = instant(iso);
  if (!d) return "—";
  // Assembled from parts: ICU's own en-IN pattern ("Thu, 5 Nov, 2026") differs between engines.
  const parts = DATE_TIME.formatToParts(d);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("weekday")}, ${get("day")} ${get("month")} ${get("year")}, ${get("hour")}:${get("minute")} ${get("dayPeriod").toLowerCase()}`;
}

const DATE_TIME = new Intl.DateTimeFormat("en-IN", {
  timeZone: ZONE,
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});

/** The Indian calendar date (YYYY-MM-DD) of a contract date-time, for the row's date tile. */
export function indianDate(iso: string | null | undefined): string | undefined {
  const d = instant(iso);
  if (!d) return undefined;
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: ZONE, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** How many sessions the widget lists (the contract returns at most five). */
export const UPCOMING_LIMIT = 5;

/**
 * The sessions still to come, soonest first, at most five: scheduled_at at or after now (and status scheduled when a
 * response carries one). The contract already filters and orders them; this keeps the widget right if a session
 * passes while the page is open or a response is longer than the contract allows.
 */
export function upcoming(sessions: readonly MySession[] | null | undefined, now: Date = new Date()): MySession[] {
  return (sessions ?? [])
    .filter((s) => {
      const status = (s as { status?: string }).status;
      const at = instant(s.scheduled_at);
      return (status === undefined || status === "scheduled") && at !== null && at.getTime() >= now.getTime();
    })
    .sort((a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime())
    .slice(0, UPCOMING_LIMIT);
}

/** Words for a session mode (contracts/openapi.yaml, SessionMode). */
export const MODE_LABEL: Record<SessionMode, string> = {
  in_person: "In person",
  online: "Online",
  phone: "Phone",
};

/** "45 min", "1 h", "1 h 30 min". null when it is not given. */
export function duration(minutes: number | null | undefined): string | null {
  if (!minutes || minutes <= 0) return null;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!h) return `${m} min`;
  return m ? `${h} h ${m} min` : `${h} h`;
}

/** The mentor's role: "Product Manager, Acme Ltd", or whichever of the two is known. null with neither. */
export function role(designation: string | null | undefined, company: string | null | undefined): string | null {
  const parts = [designation?.trim(), company?.trim()].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

/** A tel: link for a phone number as staff typed it: digits and a leading plus only. null when no digits remain. */
export function telHref(phone: string | null | undefined): string | null {
  const t = phone?.trim() ?? "";
  const digits = t.replace(/\D/g, "");
  if (!digits) return null;
  return `tel:${t.startsWith("+") ? "+" : ""}${digits}`;
}

/** The URL when it is an http(s) web address, so only web links become links (never javascript: and the like). */
export function webUrl(value: string | null | undefined): string | null {
  const t = value?.trim();
  if (!t) return null;
  try {
    const u = new URL(t);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
