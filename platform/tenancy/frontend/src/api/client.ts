/**
 * Typed client for the parts of contracts/openapi.yaml the tenancy widgets use. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class TenancyApiError extends Error {
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
  if (!res.ok) throw new TenancyApiError(res.status, res.statusText || `HTTP ${res.status}`);
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
  if (!(e instanceof TenancyApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Organisation data is not available yet.", retry: true };
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

/** contract Entitlement, as GET /organisation/entitlement answers it. */
export interface Entitlement {
  organisation_id: string;
  plan: string;
  academy_type: string;
  /** <domain>/<module> paths that are on. */
  modules: string[];
  module_names: string[];
  integrations: string[];
  limits: { users: number; students: number; storage_gb: number };
  /** In the profile but not in the plan. */
  upgradable_modules: string[];
  status: string;
  subscription_status: string | null;
}

/** GET /organisation/entitlement. Permission tenancy:organisation:read (every organisation user). */
export const getEntitlement = (signal?: AbortSignal) => get<Entitlement>("/tenancy/organisation/entitlement", signal);

/** Modules grouped by their suite (the <domain> part of the path), suites in path order. */
export function bySuite(paths: string[]): Array<{ suite: string; modules: string[] }> {
  const groups = new Map<string, string[]>();
  for (const p of paths) {
    const [suite = "other", mod = p] = p.split("/");
    groups.set(suite, [...(groups.get(suite) ?? []), mod]);
  }
  return [...groups.entries()].map(([suite, modules]) => ({ suite, modules }));
}
