/**
 * Typed client for the parts of contracts/openapi.yaml the amc-vendor-support frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types below
 * must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** One item of contract ExpiringContracts.items. */
export interface ExpiringContract {
  contract_id: string;
  number: string;
  vendor_id: string;
  title: string;
  /** ISO date */
  end_date: string;
  /** Negative when already past the end date */
  days_left: number;
  renewal_draft_exists: boolean;
}

/** contract ExpiringContracts */
export interface ExpiringContracts {
  within_days: number;
  expiring_count: number;
  expired_count: number;
  /** Soonest end date first; expired contracts (negative days_left) come first. */
  items: ExpiringContract[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class AmcVendorSupportApiError extends Error {
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
  const res = await fetch(`${API_BASE}/amc-vendor-support${path}`, { headers, signal });
  if (!res.ok) throw new AmcVendorSupportApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /stats/contracts-expiring: active contracts ending within within_days (default
 * AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS) and active contracts already past their end date, soonest first. Permission
 * amc-vendor-support:contract:read.
 */
export function getContractsExpiring(withinDays?: number, signal?: AbortSignal): Promise<ExpiringContracts> {
  return get<ExpiringContracts>(`/stats/contracts-expiring${withinDays ? `?within_days=${withinDays}` : ""}`, signal);
}
