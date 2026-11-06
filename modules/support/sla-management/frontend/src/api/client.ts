/**
 * Typed client for the parts of contracts/openapi.yaml the sla-management frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types below
 * must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** contract ClockKind */
export type ClockKind = "response" | "resolution";

/** contract Priority (helpdesk ticket priority) */
export type Priority = "low" | "medium" | "high" | "urgent";

/** contract BreachSummary.scope */
export type BreachScope = "mine" | "all";

/** One item of contract BreachSummary.most_overdue. */
export interface OverdueClock {
  clock_id: string;
  ticket_id: string;
  /** Helpdesk number, such as HD-000123 */
  ticket_number: string;
  kind: ClockKind;
  priority: Priority;
  assignee_id?: string | null;
  /** RFC 3339 date-time */
  due_at: string;
  overdue_business_minutes?: number;
}

/** contract BreachSummary */
export interface BreachSummary {
  scope: BreachScope;
  /** Running clocks past their due time */
  breached_open: number;
  /** Running clocks past their warning time, not yet breached */
  at_risk: number;
  /** Breaches recorded in the last 24 hours, whatever the clock's state now */
  breached_last_24h: number;
  /** Earliest due time first */
  most_overdue: OverdueClock[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class SlaManagementApiError extends Error {
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
  const res = await fetch(`${API_BASE}/sla-management${path}`, { headers, signal });
  if (!res.ok) throw new SlaManagementApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/breaches: running clocks that are breached or at risk, breaches in the last 24 hours and the most
 * overdue clocks. scope=mine counts clocks of tickets assigned to the caller; all (default) every clock. limit (1 to
 * 50) defaults to SLA_MANAGEMENT_BREACH_LIST_LIMIT. Permission sla-management:clock:read.
 */
export function getBreaches(scope: BreachScope = "all", limit?: number, signal?: AbortSignal): Promise<BreachSummary> {
  const query = new URLSearchParams({ scope });
  if (limit) query.set("limit", String(limit));
  return get<BreachSummary>(`/stats/breaches?${query.toString()}`, signal);
}
