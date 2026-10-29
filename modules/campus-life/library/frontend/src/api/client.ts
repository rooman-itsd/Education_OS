/**
 * Typed client for the parts of contracts/openapi.yaml the library frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** An exact decimal amount as the API sends it, for example "6.00". Never parsed into a float. */
export type Money = string;

export interface Loan {
  id: string;
  organisation_id: string;
  copy_id: string;
  title_id: string;
  title?: string | null;
  person_id: string;
  issued_at: string;
  /** A date, "YYYY-MM-DD". */
  due_on: string;
  returned_at?: string | null;
  renewals?: number;
  renewals_left?: number;
  status: "active" | "returned" | "lost";
  overdue?: boolean;
  fine_accrued?: Money;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class LibraryApiError extends Error {
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
  const res = await fetch(`${API_BASE}/library${path}`, { headers, signal });
  if (!res.ok) throw new LibraryApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /me/loans: the caller's active loans, earliest due first. Permission library:self:read. */
export function getMyLoans(signal?: AbortSignal): Promise<Loan[]> {
  return get<Loan[]>("/me/loans", signal);
}
