/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/fees-accounts) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is
 * replaced by the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** Money in the contract: a decimal string in rupees, e.g. "1500.00". Never do arithmetic on it beyond display. */
export type Money = string;

/** One unpaid or part-paid invoice in MyDues. */
export interface MyDueInvoice {
  id: string;
  number: string;
  /** Structure name and instalment label, or the first line. */
  title: string;
  balance: Money;
  /** YYYY-MM-DD. */
  due_date: string;
  overdue: boolean;
  can_pay_online: boolean;
}

/** GET /me/dues: the caller's unpaid and part-paid invoices, earliest due first. */
export interface MyDues {
  total_due: Money;
  overdue: Money;
  next_due_date: string | null;
  invoices: MyDueInvoice[];
}

export type PaymentMode = "online" | "cash" | "cheque" | "demand_draft" | "bank_transfer";

export interface FeeHeadAmount {
  fee_head_id: string;
  name: string;
  amount: Money;
}

/** GET /reports/collections: one day's collections by payment mode and fee head. */
export interface CollectionsReport {
  date: string;
  total: Money;
  count: number;
  previous_day_total: Money;
  by_mode: { mode: PaymentMode; amount: Money; count: number }[];
  by_fee_head: FeeHeadAmount[];
}

export type AgeingBucket = "not_due" | "0-30" | "31-60" | "61-90" | "90+";

/** GET /reports/outstanding: outstanding and overdue balances with ageing buckets and the largest heads. */
export interface OutstandingReport {
  as_of: string;
  outstanding: Money;
  overdue: Money;
  people_with_dues: number;
  ageing: { bucket: AgeingBucket; amount: Money; count: number }[];
  top_fee_heads: FeeHeadAmount[];
}

/** GET /reports/collection-vs-target: collected against target per period (YYYY-MM) of an academic year. */
export interface CollectionVsTargetReport {
  academic_year: string;
  target_total: Money;
  collected_total: Money;
  periods: { period: string; target: Money; collected: Money }[];
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/fees-accounts";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class FeesAccountsApiError extends Error {
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
    throw new FeesAccountsApiError(0, "The fees service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string } | undefined;
    throw new FeesAccountsApiError(res.status, body?.message ?? body?.detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** GET /me/dues. Permission fees-accounts:self:read. */
export function getMyDues(signal?: AbortSignal): Promise<MyDues> {
  return get("/me/dues", {}, signal);
}

/** GET /reports/collections; the date defaults to today in the organisation's time zone. Permission fees-accounts:report:read. */
export function getCollectionsReport(date?: string, signal?: AbortSignal): Promise<CollectionsReport> {
  return get("/reports/collections", { date }, signal);
}

/** GET /reports/outstanding, optionally for one programme. Permission fees-accounts:report:read. */
export function getOutstandingReport(programmeId?: string, signal?: AbortSignal): Promise<OutstandingReport> {
  return get("/reports/outstanding", { programme_id: programmeId }, signal);
}

/** GET /reports/collection-vs-target; the year defaults to the current academic year. Permission fees-accounts:report:read. */
export function getCollectionVsTarget(academicYear?: string, signal?: AbortSignal): Promise<CollectionVsTargetReport> {
  return get("/reports/collection-vs-target", { academic_year: academicYear }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof FeesAccountsApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Fee data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load fee data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof FeesAccountsApiError && (e.status === 401 || e.status === 403));
}
