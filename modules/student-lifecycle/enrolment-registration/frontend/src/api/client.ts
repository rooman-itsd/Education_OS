/**
 * Typed client for the parts of contracts/openapi.yaml the enrolment-registration frontend uses. The repo has no
 * OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). Calls send the session token the app shell
 * stores after sign-in.
 */

/** contract RegisteredCandidatesReport */
export interface RegisteredCandidatesReport {
  academic_period_id: string | null;
  term_name: string | null;
  total: number;
  by_type: { regular: number; supplementary: number; backlog: number };
  offerings: {
    course_offering_id: string;
    course_code: string | null;
    course_title: string | null;
    registered: number;
  }[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class EnrolmentApiError extends Error {
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
  const res = await fetch(`${API_BASE}/enrolment-registration${path}`, { headers, signal });
  if (!res.ok) throw new EnrolmentApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /reports/registered-candidates: confirmed registrations per course offering, busiest first, for the active
 * term (or every term while none is known). Permission enrolment-registration:registration:read.
 */
export function getRegisteredCandidates(limit: number, signal?: AbortSignal): Promise<RegisteredCandidatesReport> {
  return get<RegisteredCandidatesReport>(`/reports/registered-candidates?limit=${limit}`, signal);
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
  if (!(e instanceof EnrolmentApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Enrolment data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export function isAbort(e: unknown): boolean {
  return (e as { name?: string })?.name === "AbortError";
}
