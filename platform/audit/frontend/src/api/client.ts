/**
 * Typed client for the parts of contracts/openapi.yaml the audit widgets use. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class AuditApiError extends Error {
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

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}${path}`, { headers, signal });
  if (!res.ok) throw new AuditApiError(res.status, res.statusText || `HTTP ${res.status}`);
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
  if (!(e instanceof AuditApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Audit data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

/** "finance-operations" -> "Finance operations"; "user.created" -> "User created". */
export function humanise(id: string): string {
  const words = id.replace(/[-_.]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : id;
}

/** contract Record (the fields the widget shows). */
export interface AuditRecord {
  id: string;
  organisation_id: string | null;
  module: string;
  action: string;
  entity_type: string;
  entity_id: string;
  summary?: string;
  actor: string | null;
  actor_name?: string;
  occurred_at: string;
  redacted?: boolean;
}

export interface RecordPage {
  items: AuditRecord[];
  total: number;
}

/** GET /records?limit=: most recent first, scoped to the caller's organisation. Permission audit:record:read. */
export const recentRecords = (limit: number, signal?: AbortSignal) => get<RecordPage>(`/audit/records?limit=${limit}`, signal);

/** "just now", "5 min ago", "3 h ago", "2 d ago", or the date; "" for an invalid time. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const s = Math.max(0, Math.round((now.getTime() - d.getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
