/**
 * Typed client for the parts of contracts/openapi.yaml the asset-management frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** One row of contract VerificationDue.assets */
export interface DueAsset {
  asset_id: string;
  tag: string;
  name: string;
  location?: string | null;
  org_unit_id?: string | null;
  next_verification_due: string;
  overdue: boolean;
}

/** contract Cycle, the fields the widget reads */
export interface Cycle {
  id: string;
  name: string;
  due_on: string;
  status: "planned" | "in_progress" | "closed";
  counts?: { total: number; pending: number };
}

/** contract VerificationDue */
export interface VerificationDue {
  within_days: number;
  overdue_count: number;
  due_soon_count: number;
  assets: DueAsset[];
  open_cycles?: Cycle[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class AssetApiError extends Error {
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
  const res = await fetch(`${API_BASE}/asset-management${path}`, { headers, signal });
  if (!res.ok) throw new AssetApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /verifications/due: assets overdue or due for physical verification within the configured window (overdue
 * first), and open verification cycles with progress. Permission asset-management:asset:read.
 */
export function getVerificationDue(signal?: AbortSignal): Promise<VerificationDue> {
  return get<VerificationDue>("/verifications/due", signal);
}

/** "1 Nov"; "—" when the value is missing or not a date (Date gives "Invalid Date" instead of throwing). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
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
  if (!(e instanceof AssetApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Asset data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}
