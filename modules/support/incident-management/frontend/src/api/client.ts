/**
 * Typed client for the parts of contracts/openapi.yaml the incident-management frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types below
 * must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** contract Severity, most severe first */
export type Severity = "critical" | "high" | "medium" | "low";

/** The statuses GET /stats/open counts (contract OpenCounts.by_status). */
export type OpenStatus = "open" | "investigating" | "mitigated";

/** contract OpenCounts */
export interface OpenCounts {
  total_open: number;
  /** One row per severity, critical first; zero counts included. */
  by_severity: { severity: Severity; count: number }[];
  /** One row each for open, investigating and mitigated. */
  by_status: { status: OpenStatus; count: number }[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class IncidentManagementApiError extends Error {
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
  const res = await fetch(`${API_BASE}/incident-management${path}`, { headers, signal });
  if (!res.ok) throw new IncidentManagementApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/open: incidents in open, investigating or mitigated, counted by severity and by status, with the total.
 * Permission incident-management:incident:read.
 */
export function getOpenCounts(signal?: AbortSignal): Promise<OpenCounts> {
  return get<OpenCounts>("/stats/open", signal);
}
