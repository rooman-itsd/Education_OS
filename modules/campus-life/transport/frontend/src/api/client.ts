/**
 * Typed client for the parts of contracts/openapi.yaml the transport frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type NoticeKind = "delay" | "cancellation" | "route-change" | "general";

export interface Notice {
  id: string;
  organisation_id: string;
  /** Null: the notice is for every route. */
  route_id: string | null;
  route_code?: string | null;
  kind: NoticeKind;
  title: string;
  body: string;
  expires_at: string | null;
  published_at: string;
  published_by?: string;
  status: "current" | "expired" | "withdrawn";
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class TransportApiError extends Error {
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
  const res = await fetch(`${API_BASE}/transport${path}`, { headers, signal });
  if (!res.ok) throw new TransportApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
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
  if (!(e instanceof TransportApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Transport data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

/** GET /me/notices: notices for the routes of the caller's passes and for all routes, newest first. Permission transport:self:read. */
export function getMyNotices(limit = 5, signal?: AbortSignal): Promise<Notice[]> {
  return get<Notice[]>(`/me/notices?limit=${limit}`, signal);
}
