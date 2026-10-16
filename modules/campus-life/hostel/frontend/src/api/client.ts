/**
 * Typed client for the parts of contracts/openapi.yaml the hostel frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export interface Notice {
  id: string;
  organisation_id: string;
  /** Null: the notice is for every hostel. */
  hostel_id: string | null;
  title: string;
  body: string;
  expires_at: string | null;
  published_at: string;
  published_by?: string;
  status: "current" | "expired" | "withdrawn";
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class HostelApiError extends Error {
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
  const res = await fetch(`${API_BASE}/hostel${path}`, { headers, signal });
  if (!res.ok) throw new HostelApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /me/notices: the caller's current notices, newest first. Permission hostel:self:read. */
export function getMyNotices(limit = 5, signal?: AbortSignal): Promise<Notice[]> {
  return get<Notice[]>(`/me/notices?limit=${limit}`, signal);
}
