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

/** contract OrganisationStatus. */
export type OrganisationStatus = "pending_verification" | "pending_approval" | "active" | "suspended" | "archived";

/** contract Organisation, as GET /admin/organisations lists them (newest first). */
export interface Organisation {
  id: string;
  name: string;
  slug: string;
  /** The academic package in effect. */
  academy_type: string;
  /** A package change awaiting super admin approval. */
  requested_academy_type: string | null;
  country: string | null;
  status: OrganisationStatus;
  status_reason: string | null;
  plan: string | null;
  trial_ends_at: string | null;
  created_at: string | null;
}

/** GET /admin/organisations. Permission platform:organisations:read (super admin only). */
export const listOrganisations = (signal?: AbortSignal) => get<Organisation[]>("/tenancy/admin/organisations", signal);

/** Every status in the contract's order, with the words and badge tone the widgets show. */
export const STATUSES: Array<{ status: OrganisationStatus; label: string; tone: "warning" | "info" | "success" | "danger" | "neutral" }> = [
  { status: "pending_verification", label: "Pending verification", tone: "info" },
  { status: "pending_approval", label: "Pending approval", tone: "warning" },
  { status: "active", label: "Active", tone: "success" },
  { status: "suspended", label: "Suspended", tone: "danger" },
  { status: "archived", label: "Archived", tone: "neutral" },
];
export const statusInfo = (s: string) => STATUSES.find((x) => x.status === s) ?? { status: s as OrganisationStatus, label: humanise(s), tone: "neutral" as const };

/** One thing waiting for the super admin: a new registration, or an active organisation's package change. */
export interface Approval {
  organisation: Organisation;
  kind: "registration" | "package-change";
  /** The academic package to approve. */
  package: string;
}

/**
 * What waits for the super admin's approval, oldest first: registrations in pending_approval, and organisations
 * that asked for another academic package (requested_academy_type), whatever their status but archived.
 */
export function approvalQueue(orgs: Organisation[]): Approval[] {
  const out: Approval[] = [];
  for (const o of orgs) {
    if (o.status === "pending_approval") out.push({ organisation: o, kind: "registration", package: o.requested_academy_type ?? o.academy_type });
    else if (o.requested_academy_type && o.status !== "archived") out.push({ organisation: o, kind: "package-change", package: o.requested_academy_type });
  }
  return out.sort((a, b) => (a.organisation.created_at ?? "").localeCompare(b.organisation.created_at ?? ""));
}

/** How many organisations are in each status, every status listed (zero included), in the contract's order. */
export function countByStatus(orgs: Organisation[]): Array<{ status: OrganisationStatus; count: number }> {
  return STATUSES.map(({ status }) => ({ status, count: orgs.filter((o) => o.status === status).length }));
}

/** The n most recently registered organisations, newest first. */
export function newest(orgs: Organisation[], n = 5): Organisation[] {
  return [...orgs].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")).slice(0, n);
}

/** "just now", "5 min ago", "3 h ago", "2 d ago", or the date; "" for a missing or invalid time. */
export function timeAgo(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const s = Math.max(0, Math.round((now.getTime() - d.getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** Two-letter initials for an organisation's row tile: "Rooman Music Academy" -> "RM". */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] ?? "") + (words[1]?.[0] ?? words[0]?.[1] ?? "")).toUpperCase() || "?";
}
