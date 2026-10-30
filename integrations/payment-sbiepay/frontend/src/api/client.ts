/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/payment-sbiepay) the dashboard
 * widget uses. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is
 * replaced by the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** Money in the contract: a decimal string in rupees, e.g. "1500.00". Arithmetic on it is done in whole paise (see format.ts). */
export type Money = string;

/** How many payments and their combined amount. */
export interface CountAmount {
  count: number;
  amount: Money;
}

/**
 * GET /reconciliation/summary: one day's fee and subscription payments for the Finance Staff widget.
 * Days are UTC (application/service.py, summary).
 */
export interface ReconciliationSummary {
  /** YYYY-MM-DD: the day summarised. */
  date: string;
  /** Payments that succeeded (or were later refunded) and completed that day. */
  succeeded: CountAmount;
  /** Payments started that day that are still open (created or pending at the gateway). */
  pending: CountAmount;
  /** Payments that failed that day. The contract gives no amount. */
  failed: { count: number };
  /** The succeeded payments that are settled into the merchant account. */
  settled: CountAmount;
  /** Mismatches found by the latest reconciliation run for that settlement date; 0 when there was no run. */
  mismatches: number;
  /** ISO date-time the latest run for that date started; null when the day has not been reconciled. */
  last_run_at: string | null;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/payment-sbiepay";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class PaymentApiError extends Error {
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
    throw new PaymentApiError(0, "The payment service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from FastAPI and the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string | { message?: string } } | undefined;
    throw new PaymentApiError(res.status, body?.message ?? (typeof body?.detail === "string" ? body.detail : body?.detail?.message) ?? res.statusText);
  }
  return (await res.json()) as T;
}

/**
 * GET /reconciliation/summary. Permission payment-sbiepay:payment:read.
 * Without `date` (YYYY-MM-DD) the adapter summarises today in UTC.
 */
export function getReconciliationSummary(date?: string, signal?: AbortSignal): Promise<ReconciliationSummary> {
  return get("/reconciliation/summary", { date }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof PaymentApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Payment data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load payment data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof PaymentApiError && (e.status === 401 || e.status === 403));
}
