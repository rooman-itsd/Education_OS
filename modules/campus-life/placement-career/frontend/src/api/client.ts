/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/placement-career) the dashboard widgets
 * use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the
 * generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** Decimal string in rupees, not negative (Money). */
export type Money = string;

export type ApplicationStatus =
  | "applied"
  | "shortlisted"
  | "in_process"
  | "offered"
  | "accepted"
  | "declined"
  | "rejected"
  | "withdrawn";

/** Eligibility: criteria shown to students, not enforced. Every field is optional. */
export interface Eligibility {
  programmes?: string[];
  graduating_years?: number[];
  min_cgpa?: number | null;
  max_active_backlogs?: number | null;
  notes?: string | null;
}

/** CompanySummary: what every reader of openings and drives sees of a company (no contacts). */
export interface CompanySummary {
  id: string;
  name: string;
  industry: string | null;
  website: string | null;
}

/** MyOpening: an open opening that still takes applications, with the caller's own application if any. */
export interface MyOpening {
  id: string;
  title: string;
  company: CompanySummary;
  drive: { id: string; title: string; scheduled_on: string; venue: string | null; eligibility?: Eligibility } | null;
  location: string | null;
  ctc_per_annum: Money | null;
  /** YYYY-MM-DD, Indian business date: applications are taken up to and including it. */
  applications_close_on: string;
  eligibility?: Eligibility;
  /** Null if the caller has not applied. */
  my_application: { id: string; status: ApplicationStatus } | null;
}

/** MyOpeningPage: GET /me/openings, a cursor page, soonest closing first. */
export interface MyOpeningPage {
  items: MyOpening[];
  next_cursor: string | null;
}

/** CountsByApplicationStatus. */
export type CountsByApplicationStatus = Record<ApplicationStatus, number>;

/** One drive of DrivesUpcomingReport. */
export interface UpcomingDrive {
  id: string;
  title: string;
  company: CompanySummary;
  /** YYYY-MM-DD, Indian business date. */
  scheduled_on: string;
  venue: string | null;
  registration_closes_on: string | null;
  openings_count: number;
  applications: CountsByApplicationStatus;
}

/** DrivesUpcomingReport: GET /reports/drives-upcoming, scheduled drives from today (IST), soonest first. */
export interface DrivesUpcomingReport {
  /** Scheduled drives dated today to today + 30 (IST), over all of them, not only the ones listed. */
  next_30_days: number;
  drives: UpcomingDrive[];
}

/** One opening of OpeningsSummaryReport.closing_soon. */
export interface ClosingSoon {
  id: string;
  title: string;
  company_name: string;
  applications_close_on: string;
  applications_count: number;
}

/** OpeningsSummaryReport: GET /reports/openings-summary. */
export interface OpeningsSummaryReport {
  openings: { draft: number; open: number; closed: number };
  applications: CountsByApplicationStatus;
  /** Distinct students with an accepted offer. */
  students_placed: number;
  /** Open openings, soonest applications_close_on first. */
  closing_soon: ClosingSoon[];
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/placement-career";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class PlacementApiError extends Error {
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

async function get<T>(path: string, query: Record<string, string | undefined> = {}, signal?: AbortSignal): Promise<T> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined) params.set(k, v);
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
    throw new PlacementApiError(0, "The placement-career service could not be reached.");
  }
  if (!res.ok) {
    // The contract's errors are { detail: { code, message } }; FastAPI's validation errors and the gateway's are { detail }.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string | { message?: string } } | undefined;
    throw new PlacementApiError(res.status, body?.message ?? (typeof body?.detail === "string" ? body.detail : body?.detail?.message) ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** GET /me/openings, first page of `limit` openings (1 to 200). Permission placement-career:self:read. */
export function getMyOpenings(limit: number, signal?: AbortSignal): Promise<MyOpeningPage> {
  return get("/me/openings", { limit: String(limit) }, signal);
}

/** GET /reports/openings-summary listing `limit` openings closing soonest (1 to 50). Permission placement-career:report:read. */
export function getOpeningsSummary(limit: number, signal?: AbortSignal): Promise<OpeningsSummaryReport> {
  return get("/reports/openings-summary", { limit: String(limit) }, signal);
}

/** GET /reports/drives-upcoming listing `limit` drives (1 to 50). Permission placement-career:report:read. */
export function getDrivesUpcoming(limit: number, signal?: AbortSignal): Promise<DrivesUpcomingReport> {
  return get("/reports/drives-upcoming", { limit: String(limit) }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function describeFailure(e: unknown): string {
  if (e instanceof PlacementApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Placement data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load placement data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof PlacementApiError && (e.status === 401 || e.status === 403));
}
