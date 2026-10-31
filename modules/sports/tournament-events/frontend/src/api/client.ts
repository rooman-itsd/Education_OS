/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/tournament-events) the dashboard widgets
 * use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the
 * generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** A page of a list endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
}

/**
 * Drafts are visible only to holders of tournament:write. `ongoing` and `completed` are published tournaments read
 * from their dates in the institution's local date.
 */
export type TournamentStatus = "draft" | "published" | "ongoing" | "completed" | "cancelled";

export type TournamentLevel = "intra_institution" | "inter_university" | "state" | "national" | "international";

/** contract Tournament (the fields the widgets read). */
export interface Tournament {
  id: string;
  name: string;
  discipline: string;
  level: TournamentLevel;
  /** YYYY-MM-DD, the institution's local dates. */
  start_date: string;
  end_date: string;
  status: TournamentStatus;
  venue?: string;
  hosting?: "home" | "away" | "neutral";
  /** YYYY-MM-DD; entries are taken until this day, inclusive. */
  registration_closes_on?: string;
}

export type EntryStatus = "pending" | "confirmed" | "withdrawn";

/** contract Entry (the fields the widgets read). Athletes get only the entries that name them. */
export interface Entry {
  id: string;
  category: string;
  team_name?: string;
  athlete_ids: string[];
  status: EntryStatus;
}

export type FixtureStatus = "scheduled" | "in_progress" | "completed" | "postponed" | "cancelled";

/** contract Fixture (the fields the widgets read). */
export interface Fixture {
  id: string;
  round: string;
  category?: string;
  entry_ids: string[];
  /** date-time */
  scheduled_at: string;
  venue?: string;
  status: FixtureStatus;
}

/**
 * contract CalendarEntry. A tournament runs from `starts_at` (the local start of its first day) to `ends_at` (the
 * local start of the day after its last); a fixture has only `starts_at`.
 */
export interface CalendarEntry {
  kind: "tournament" | "fixture";
  id: string;
  tournament_id?: string;
  title: string;
  /** date-time */
  starts_at: string;
  ends_at?: string;
  venue?: string;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/tournament-events";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class TournamentEventsApiError extends Error {
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

async function get<T>(path: string, query: Record<string, string | number | undefined> = {}, signal?: AbortSignal): Promise<T> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined) params.set(k, String(v));
  const qs = params.toString();
  const t = token();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, {
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new TournamentEventsApiError(0, "The tournament service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string } | undefined;
    throw new TournamentEventsApiError(res.status, body?.message ?? body?.detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

/**
 * GET /tournaments, by start date. Drafts are left out for callers without tournament:write; `status` is the
 * effective status (published means not started yet). Permission tournament-events:tournament:read.
 */
export function listTournaments(
  query: { status?: TournamentStatus; from?: string; to?: string; limit: number },
  signal?: AbortSignal,
): Promise<Page<Tournament>> {
  return get("/tournaments", query, signal);
}

/** GET /tournaments/{id}/entries, by category. Athletes get only their own entries. Permission tournament-events:entry:read. */
export function listEntries(tournamentId: string, query: { limit: number }, signal?: AbortSignal): Promise<Page<Entry>> {
  return get(`/tournaments/${encodeURIComponent(tournamentId)}/entries`, query, signal);
}

/** GET /tournaments/{id}/fixtures, by time; `from`/`to` are local days. Permission tournament-events:fixture:read. */
export function listFixtures(
  tournamentId: string,
  query: { from?: string; to?: string; limit: number },
  signal?: AbortSignal,
): Promise<Page<Fixture>> {
  return get(`/tournaments/${encodeURIComponent(tournamentId)}/fixtures`, query, signal);
}

/**
 * GET /calendar: published tournaments with a day in the period and their fixtures that are not cancelled, by time.
 * Not paged; the backend refuses a period longer than 366 days. Permission tournament-events:tournament:read.
 */
export function getCalendar(query: { from: string; to: string }, signal?: AbortSignal): Promise<{ items: CalendarEntry[] }> {
  return get("/calendar", query, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof TournamentEventsApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Tournament data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load tournament data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof TournamentEventsApiError && (e.status === 401 || e.status === 403));
}
