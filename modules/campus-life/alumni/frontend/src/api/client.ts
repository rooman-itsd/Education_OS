/**
 * Typed client for the part of contracts/openapi.yaml (servers: /api/v1/alumni) the dashboard widget uses. The repo
 * has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the generated client and
 * the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** components.schemas.MentorCard: the mentor as their assigned mentee sees them, contact details included. */
export interface MentorCard {
  id: string;
  full_name: string;
  graduation_year: number;
  programme?: string | null;
  current_company?: string | null;
  current_designation?: string | null;
  industry?: string | null;
  city?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
}

/** components.schemas.SessionMode */
export type SessionMode = "in_person" | "online" | "phone";

/** components.schemas.MySession: a session as the mentee sees it (no staff notes). */
export interface MySession {
  id: string;
  /** UTC date-time. */
  scheduled_at: string;
  duration_minutes?: number | null;
  mode: SessionMode;
  /** A room, an address or a meeting link. */
  location?: string | null;
  topic?: string | null;
}

/** components.schemas.MyMentoring.assignment when it is not null. */
export interface MyAssignment {
  id: string;
  /** YYYY-MM-DD, a calendar date in Asia/Kolkata. */
  started_on: string;
  focus?: string | null;
  mentor: MentorCard;
}

/** components.schemas.MyMentoring */
export interface MyMentoring {
  /** null when the caller has no active mentor: the widget's empty state. */
  assignment: MyAssignment | null;
  /** Status scheduled and scheduled_at at or after now, soonest first, at most five. */
  upcoming_sessions: MySession[];
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/alumni";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/**
 * A failed call. `status` is the HTTP status, or 0 when the service could not be reached. `code` is the contract's
 * error code ({"detail": {"code", "message"}}); a gateway or an unmounted module answers without one.
 */
export class AlumniApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
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

type ErrorBody = { code?: string; message?: string; detail?: string | { code?: string; message?: string } };

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const t = token();
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {}, signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new AlumniApiError(0, "The alumni service could not be reached.");
  }
  if (!res.ok) {
    // {"detail": {"code", "message"}} from the contract; {"detail": "Not Found"} from the gateway or an unmounted module.
    const body = (await res.json().catch(() => undefined)) as ErrorBody | undefined;
    const detail = typeof body?.detail === "object" ? body.detail : undefined;
    const message = detail?.message ?? body?.message ?? (typeof body?.detail === "string" ? body.detail : undefined) ?? res.statusText;
    throw new AlumniApiError(res.status, message, detail?.code ?? body?.code);
  }
  return (await res.json()) as T;
}

/**
 * GET /me/mentoring: the caller's active assignment with the mentor's contact details (null without one) and its next
 * five upcoming sessions, soonest first. Permission alumni:self:read.
 */
export function getMyMentoring(signal?: AbortSignal): Promise<MyMentoring> {
  return get("/me/mentoring", signal);
}

/** What the widget's error state says, and whether trying again can help. */
export interface Failure {
  message: string;
  retry: boolean;
}

/**
 * Words for a failed call. A missing or unreachable service (404, 502, 503, no answer) is "not available yet";
 * retrying cannot fix a missing or expired session (401) or a missing permission (403). Server wording (a 500's
 * message, a gateway page) is never the headline.
 */
export function describeFailure(e: unknown): Failure {
  if (e instanceof AlumniApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) {
      return { message: "Alumni data is not available yet.", retry: true };
    }
    if (e.status === 401) return { message: "Sign in again to see this.", retry: false };
    if (e.status === 403) return { message: "You do not have access to this.", retry: false };
  }
  return { message: "Could not load alumni data.", retry: true };
}
