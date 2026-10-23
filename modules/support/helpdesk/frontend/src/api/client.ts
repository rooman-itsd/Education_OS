/**
 * Typed client for the parts of contracts/openapi.yaml the helpdesk frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type Priority = "low" | "medium" | "high" | "urgent";
export type OpenScope = "mine" | "my_queues" | "all";

/** One item of OpenByPriority.rows. */
export interface PriorityRow {
  priority: Priority;
  /** new + in_progress + on_hold */
  open: number;
  unassigned: number;
  assigned_to_me: number;
  on_hold: number;
  oldest_created_at?: string | null;
}

/** contract OpenByPriority */
export interface OpenByPriority {
  scope: OpenScope;
  total_open: number;
  /** One row per priority, urgent first; priorities with no open tickets have zero counts. */
  rows: PriorityRow[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class HelpdeskApiError extends Error {
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
  const res = await fetch(`${API_BASE}/helpdesk${path}`, { headers, signal });
  if (!res.ok) throw new HelpdeskApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/open-by-priority: open tickets counted per priority, urgent first. Permission helpdesk:ticket:read;
 * scope=all also needs helpdesk:ticket:read-all. Without a scope the API uses my_queues.
 */
export function getOpenByPriority(scope?: OpenScope, signal?: AbortSignal): Promise<OpenByPriority> {
  return get<OpenByPriority>(`/stats/open-by-priority${scope ? `?scope=${scope}` : ""}`, signal);
}
