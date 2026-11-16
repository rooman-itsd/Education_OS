/**
 * Typed client for the parts of contracts/openapi.yaml the regulatory-reports frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types below
 * must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

export type FilingStatus = "open" | "in_preparation" | "under_review" | "submitted" | "acknowledged" | "not_applicable";
export type Scope = "mine" | "all";

/** contract FilingSummary */
export interface FilingSummary {
  filing_id: string;
  obligation_title: string;
  authority: string;
  period_label: string;
  /** ISO date */
  due_on: string;
  status: FilingStatus;
  overdue: boolean;
}

/** contract DueStats */
export interface DueStats {
  scope: Scope;
  due_soon_days: number;
  due_soon: number;
  overdue: number;
  /** Up to ten filings, soonest due first */
  soonest: FilingSummary[];
}

/** contract Calendar */
export interface Calendar {
  from: string;
  to: string;
  /** Filings due in the range, by due date */
  items: FilingSummary[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class RegulatoryReportsApiError extends Error {
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
  const res = await fetch(`${API_BASE}/regulatory-reports${path}`, { headers, signal });
  if (!res.ok) throw new RegulatoryReportsApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/due: filings not yet submitted that are due within REGULATORY_REPORTS_DUE_SOON_DAYS or overdue.
 * scope=mine (default) counts the caller's own; scope=all also needs regulatory-reports:data:read.
 * Permission regulatory-reports:stats:read.
 */
export function getDue(scope: Scope = "mine", signal?: AbortSignal): Promise<DueStats> {
  return get<DueStats>(`/stats/due?scope=${scope}`, signal);
}

/**
 * GET /calendar: filings by due date between from and to (ISO dates, at most REGULATORY_REPORTS_CALENDAR_MAX_DAYS
 * apart). Permission regulatory-reports:data:read and regulatory-reports:stats:read.
 */
export function getCalendar(from: string, to: string, signal?: AbortSignal): Promise<Calendar> {
  return get<Calendar>(`/calendar?from=${from}&to=${to}`, signal);
}
