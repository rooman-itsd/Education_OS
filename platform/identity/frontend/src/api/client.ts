/**
 * Typed client for the parts of contracts/openapi.yaml the identity widgets use. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class IdentityApiError extends Error {
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
  if (!res.ok) throw new IdentityApiError(res.status, res.statusText || `HTTP ${res.status}`);
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
  if (!(e instanceof IdentityApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "User data is not available yet.", retry: true };
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

/** A user of the caller's organisation, as GET /users answers it. */
export interface User {
  id: string;
  organisation_id: string | null;
  email: string;
  name: string;
  roles: string[];
  is_super_admin: boolean;
  status: string;
  created_at: string | null;
}

/** GET /users: the organisation's users. Permission identity:user:read. */
export const listUsers = (signal?: AbortSignal) => get<User[]>("/identity/users", signal);

/** Users per role, largest first; a user holding several roles counts in each. */
export function byRole(users: User[]): Array<{ role: string; count: number }> {
  const counts = new Map<string, number>();
  for (const u of users) for (const r of u.roles.length ? u.roles : ["(no role)"]) counts.set(r, (counts.get(r) ?? 0) + 1);
  return [...counts.entries()].map(([role, count]) => ({ role, count })).sort((a, b) => b.count - a.count || a.role.localeCompare(b.role));
}
