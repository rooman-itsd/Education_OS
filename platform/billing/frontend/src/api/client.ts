/**
 * Typed client for the parts of contracts/openapi.yaml the billing widgets use. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type SubscriptionStatus = "trialing" | "active" | "past_due" | "cancelled" | "read_only";

/** contract Plan (the fields the widgets show). */
export interface Plan {
  id: string;
  title: string;
  description: string;
  price_per_month: number;
  currency: string;
  trial_days: number | null;
  limits: { users: number; students: number; storage_gb: number };
  published: boolean;
}

/** contract Subscription, as GET /subscription answers it. */
export interface Subscription {
  id: string;
  organisation_id: string;
  plan: string;
  status: SubscriptionStatus;
  trial_ends_at: string | null;
  current_period_ends_at: string | null;
  pending_plan: string | null;
}

/** contract Invoice (0.1.1). */
export interface Invoice {
  id: string;
  organisation_id: string;
  plan: string;
  amount: number;
  currency: string;
  status: "draft" | "due" | "paid" | "void";
  issued_at: string;
  period_start: string;
  period_end: string;
  payment_reference: string | null;
  document_id: string | null;
}

export interface UpgradeResult {
  activated: boolean;
  payment_url: string | null;
  reference: string;
}

/** The parts of tenancy's Entitlement and identity's User the usage widget needs. */
export interface Entitlement {
  plan: string;
  modules: string[];
  upgradable_modules: string[];
  limits: { users: number; students: number; storage_gb: number };
}
export interface User {
  id: string;
  roles: string[];
  status: string;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class BillingApiError extends Error {
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

async function request<T>(path: string, init: { method?: string; json?: unknown } = {}, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body: string | undefined;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${API_BASE}${path}`, { method: init.method ?? "GET", headers, body, signal });
  if (!res.ok) throw new BillingApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /plans: the published price list (public). */
export const getPlans = (signal?: AbortSignal) => request<Plan[]>("/billing/plans", {}, signal);
/** GET /subscription. Permission billing:subscription:read. */
export const getSubscription = (signal?: AbortSignal) => request<Subscription>("/billing/subscription", {}, signal);
/** GET /invoices, newest first. Permission billing:subscription:read. */
export const getInvoices = (signal?: AbortSignal) => request<Invoice[]>("/billing/invoices", {}, signal);
/** POST /subscription/upgrade. Permission billing:subscription:manage. */
export const upgrade = (plan: string) => request<UpgradeResult>("/billing/subscription/upgrade", { method: "POST", json: { plan } });
/** GET /tenancy/organisation/entitlement. Permission tenancy:organisation:read (every organisation user). */
export const getEntitlement = (signal?: AbortSignal) => request<Entitlement>("/tenancy/organisation/entitlement", {}, signal);
/** GET /identity/users. Permission identity:user:read. */
export const listUsers = (signal?: AbortSignal) => request<User[]>("/identity/users", {}, signal);

/** "₹24,999" */
export function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    return `${amount} ${currency}`;
  }
}

/** "11 Nov 2026"; "—" when missing or not a date (Date gives "Invalid Date" instead of throwing). */
export function longDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
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
  if (!(e instanceof BillingApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Billing data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}
