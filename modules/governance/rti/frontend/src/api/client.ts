/**
 * Typed client for the parts of contracts/openapi.yaml the rti frontend uses. The repo has no OpenAPI generator yet;
 * when packages/contracts ships one, this file is replaced by the generated client and the types below must keep
 * matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

export type RequestStatus =
  | "received"
  | "assigned"
  | "responded"
  | "appealed"
  | "appeal_decided"
  | "transferred"
  | "closed";

/** contract NearingDeadline.items[]: no applicant data and no request content. */
export interface DeadlineItem {
  request_id: string;
  /** Per-organisation number, such as RTI-000045 */
  number: string;
  status: RequestStatus;
  /** ISO date-time (UTC): the end of the due date in India */
  due_at: string;
  overdue: boolean;
}

/** contract NearingDeadline */
export interface NearingDeadline {
  within_days: number;
  /** Open requests and appeals due within within_days */
  due_soon: number;
  overdue: number;
  /** The soonest ten, longest overdue first */
  items: DeadlineItem[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class RtiApiError extends Error {
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
  const res = await fetch(`${API_BASE}/rti${path}`, { headers, signal });
  if (!res.ok) throw new RtiApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/nearing-deadline: open requests that are overdue or due within RTI_NEARING_DEADLINE_DAYS, as counts and
 * a list of request numbers, statuses and due dates. Permission rti:stats:read.
 */
export function getNearingDeadline(signal?: AbortSignal): Promise<NearingDeadline> {
  return get<NearingDeadline>("/stats/nearing-deadline", signal);
}
