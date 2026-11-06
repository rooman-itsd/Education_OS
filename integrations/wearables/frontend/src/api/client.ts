/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/wearables) the dashboard widget uses. The repo has no
 * OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types below
 * must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell stores after
 * sign-in.
 */

/** AlertKind in the contract. */
export type AlertKind = "link_expired" | "link_revoked" | "sync_failing" | "no_recent_data" | "not_linked";

/** Alert in the contract: a status and a date, never a reading. */
export interface Alert {
  person_id: string;
  provider: string | null;
  kind: AlertKind;
  /** ISO date-time the condition began. */
  since: string;
  last_synced_at: string | null;
}

/** AlertPage in the contract. */
export interface AlertPage {
  items: Alert[];
  next_cursor: string | null;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/wearables";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class WearablesApiError extends Error {
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
    throw new WearablesApiError(0, "The device service could not be reached.");
  }
  if (!res.ok) {
    // Error { code, detail } from the contract.
    const body = (await res.json().catch(() => undefined)) as { detail?: string } | undefined;
    throw new WearablesApiError(res.status, typeof body?.detail === "string" ? body.detail : res.statusText);
  }
  return (await res.json()) as T;
}

/**
 * GET /alerts. Permission wearables:alert:read. `personIds` narrows it to a squad (the contract allows 200); without it the
 * coach sees the problems of every athlete of the organisation, which are statuses and dates only.
 */
export function getAlerts(options: { personIds?: string[]; limit?: number } = {}, signal?: AbortSignal): Promise<AlertPage> {
  const ids = options.personIds?.slice(0, 200).join(",");
  return get("/alerts", { person_id: ids || undefined, limit: options.limit === undefined ? undefined : String(options.limit) }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof WearablesApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Device alerts are not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load device alerts.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof WearablesApiError && (e.status === 401 || e.status === 403));
}
