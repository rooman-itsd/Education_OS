import type { AlertKind } from "../api/client";

/** A contract date-time as "4 Nov 2026" in the viewer's time zone; null when it is missing or unreadable. */
export function dayOf(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** What each kind of alert says, in words (never colour alone). */
export const KIND_LABEL: Record<AlertKind, string> = {
  link_expired: "Link expired",
  link_revoked: "Link removed",
  sync_failing: "Not syncing",
  no_recent_data: "No recent data",
  not_linked: "Not connected",
};

/** Provider ids as people know them ("google-health" is Fitbit). */
export const PROVIDER_LABEL: Record<string, string> = { garmin: "Garmin", polar: "Polar", "google-health": "Fitbit", strava: "Strava" };

/** A short, stable handle for an athlete the widget has no name for: the last six characters of their id. */
export function athleteHandle(personId: string): string {
  return `Athlete …${personId.replace(/-/g, "").slice(-6)}`;
}
