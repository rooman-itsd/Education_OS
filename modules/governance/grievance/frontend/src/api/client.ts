/**
 * Typed client for the parts of contracts/openapi.yaml the grievance frontend uses: the two count endpoints behind the
 * dashboard widgets. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by
 * the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell stores
 * after sign-in. Both endpoints return counts only, never case content.
 */

export type Track = "student_grievance" | "ragging" | "sexual_harassment";
export type CommitteeKind = "sgrc" | "anti_ragging" | "icc" | "ombudsperson";
export type CaseStatus =
  | "submitted"
  | "acknowledged"
  | "under_inquiry"
  | "decided"
  | "appealed"
  | "appeal_decided"
  | "closed"
  | "not_admitted"
  | "withdrawn";

/** contract OpenByCommittee.committees[] */
export interface CommitteeCount {
  committee_id: string;
  name: string;
  kind: CommitteeKind;
  open: number;
  overdue: number;
  by_status: { status: CaseStatus; count: number }[];
}

/** contract OpenByCommittee */
export interface OpenByCommittee {
  total_open: number;
  committees: CommitteeCount[];
}

/** contract OpenByTrack.tracks[] */
export interface TrackCount {
  track: Track;
  open: number;
  overdue: number;
}

/** contract OpenByTrack */
export interface OpenByTrack {
  total_open: number;
  overdue: number;
  tracks: TrackCount[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class GrievanceApiError extends Error {
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
  const res = await fetch(`${API_BASE}/grievance${path}`, { headers, signal });
  if (!res.ok) throw new GrievanceApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/open-by-committee: open cases per committee and status, with overdue counts. Appealed cases count under
 * the ombudsperson committee. Permission grievance:stats:read.
 */
export function getOpenByCommittee(signal?: AbortSignal): Promise<OpenByCommittee> {
  return get<OpenByCommittee>("/stats/open-by-committee", signal);
}

/** GET /stats/open: open cases per track, with overdue counts. Permission grievance:stats:read. */
export function getOpenByTrack(signal?: AbortSignal): Promise<OpenByTrack> {
  return get<OpenByTrack>("/stats/open", signal);
}
