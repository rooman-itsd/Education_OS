/**
 * Typed client for the parts of contracts/openapi.yaml the facility-booking frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** contract BookingStatus */
export type BookingStatus = "pending" | "confirmed" | "rejected" | "cancelled" | "checked_in" | "completed" | "no_show";

/** contract Booking, the fields the widgets read */
export interface Booking {
  id: string;
  resource_id: string;
  resource_name?: string | null;
  start_at: string;
  end_at: string;
  status: BookingStatus;
  title?: string | null;
  party_size?: number | null;
}

/** contract BookingPage */
export interface BookingPage {
  items: Booking[];
  total: number;
  page: number;
  page_size: number;
}

/** contract Summary */
export interface Summary {
  date: string;
  bookings_today: number;
  pending_approval: number;
  checked_in_now: number;
  no_shows_today: number;
  resources_out_of_service: number;
}

/** Today's bookings that still matter on a dashboard: cancelled and rejected ones are left out. */
export const LIVE_STATUSES: BookingStatus[] = ["pending", "confirmed", "checked_in", "completed", "no_show"];

/** Bookings still ahead or under way: finished, cancelled and rejected ones are left out. */
export const UPCOMING_STATUSES: BookingStatus[] = ["pending", "confirmed", "checked_in"];

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class BookingApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}/facility-booking${path}`, { headers, signal });
  if (!res.ok) throw new BookingApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /bookings?scope=managed&date=today: today's bookings on the resources the caller approves or, with
 * facility-booking:booking:read-all, on every resource. Permission facility-booking:booking:read.
 */
export function listBookingsToday(pageSize: number, signal?: AbortSignal): Promise<BookingPage> {
  const status = LIVE_STATUSES.join(",");
  return get<BookingPage>(`/bookings?scope=managed&date=today&status=${status}&page_size=${pageSize}`, signal);
}

/**
 * GET /bookings?scope=<scope>&from=now: bookings not yet over, earliest first. scope=mine is the caller's own (booked
 * by or for them); scope=managed is those on the resources the caller approves, or every resource with
 * facility-booking:booking:read-all. Permission facility-booking:booking:read.
 */
export function listUpcomingBookings(scope: "mine" | "managed", pageSize: number, signal?: AbortSignal): Promise<BookingPage> {
  const status = UPCOMING_STATUSES.join(",");
  return get<BookingPage>(`/bookings?scope=${scope}&from=now&status=${status}&page_size=${pageSize}`, signal);
}

/** GET /summary?date=today: counts over the resources the caller manages or approves. Permission facility-booking:booking:read. */
export function getSummary(signal?: AbortSignal): Promise<Summary> {
  return get<Summary>("/summary?date=today", signal);
}

/** "09:00" in the viewer's time; "—" when the value is missing or not a date. */
export function clock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

/**
 * A booking's time window, "09:00–10:30". A start or end on another day (an overnight booking that overlaps today)
 * carries its date, "28 Oct 22:00–02:00", so the row cannot be read as a window within today.
 */
export function timeWindow(startIso: string | null | undefined, endIso: string | null | undefined, now = new Date()): string {
  const part = (iso: string | null | undefined) => {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    const sameDay = d.toDateString() === now.toDateString();
    return sameDay ? clock(iso) : `${d.toLocaleDateString("en-GB", { day: "numeric", month: "short" })} ${clock(iso)}`;
  };
  return `${part(startIso)}–${part(endIso)}`;
}

/** The day a booking starts, in the viewer's time: "Today", "Tomorrow" or "Fri 31 Oct"; "—" when missing or not a date. */
export function dayLabel(iso: string | null | undefined, now = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  if (d.toDateString() === now.toDateString()) return "Today";
  if (d.toDateString() === tomorrow.toDateString()) return "Tomorrow";
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }).replace(",", "");
}

export interface Failure {
  title: string;
  detail?: string;
  retry: boolean;
}

/**
 * What a widget's error state says, as the other modules' widgets do. A missing or unreachable service (404, 502,
 * 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof BookingApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Booking data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}
