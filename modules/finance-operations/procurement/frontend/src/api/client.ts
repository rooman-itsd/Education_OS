/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/procurement) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is
 * replaced by the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** Money in the contract: a decimal string in rupees, e.g. "1500.00". Arithmetic on it is done in whole paise (see format.ts). */
export type Money = string;

export type PurchaseOrderStatus =
  | "draft"
  | "submitted"
  | "returned"
  | "issued"
  | "partially_received"
  | "received"
  | "closed"
  | "cancelled";

/** CountValue: how many items and their combined value. */
export interface CountValue {
  count: number;
  value: Money;
}

/** One of the oldest pending orders in the pending report. */
export interface PendingOrder {
  id: string;
  /** Purchase order number. */
  number: string;
  vendor_name: string;
  status: PurchaseOrderStatus;
  total: Money;
  /** YYYY-MM-DD: the date the order has been pending since. */
  since: string;
}

/**
 * GET /reports/purchase-orders-pending: orders awaiting approval, issued orders awaiting delivery (with the
 * overdue ones) and approved invoices awaiting payment, with the oldest pending orders.
 */
export interface PendingReport {
  awaiting_approval: CountValue;
  awaiting_delivery: CountValue;
  overdue_delivery: CountValue;
  invoices_awaiting_payment: CountValue;
  /** Up to ten oldest pending orders. */
  oldest: PendingOrder[];
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/procurement";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class ProcurementApiError extends Error {
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
    throw new ProcurementApiError(0, "The procurement service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string | { message?: string } } | undefined;
    throw new ProcurementApiError(res.status, body?.message ?? (typeof body?.detail === "string" ? body.detail : body?.detail?.message) ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** GET /reports/purchase-orders-pending. Permission procurement:report:read. */
export function getPurchaseOrdersPending(signal?: AbortSignal): Promise<PendingReport> {
  return get("/reports/purchase-orders-pending", {}, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof ProcurementApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Procurement data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load procurement data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof ProcurementApiError && (e.status === 401 || e.status === 403));
}
