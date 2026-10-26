/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/budget-grants) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is
 * replaced by the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** Money in the contract: a decimal string in rupees, e.g. "1500.00". Arithmetic on it is done in whole paise (see format.ts). */
export type Money = string;

export type InvestigatorRole = "principal" | "co_investigator";

/** One item of GET /me/grants: a grant where the caller is principal or co-investigator. */
export interface MyGrant {
  id: string;
  /** Sanction or project number. */
  code: string;
  title: string;
  /** Funding agency name. */
  funder: string;
  my_role: InvestigatorRole;
  sanctioned_amount: Money;
  spent_total: Money;
  balance: Money;
  /** YYYY-MM-DD. */
  end_date: string;
  /** YYYY-MM-DD, or null when no utilisation certificate is due. */
  next_uc_due: string | null;
}

/** One budget head in the budget-vs-spend report. */
export interface BudgetHeadSpend {
  budget_head_id: string;
  name: string;
  allocated: Money;
  committed: Money;
  spent: Money;
}

/** Grant totals in the budget-vs-spend report. */
export interface GrantTotals {
  active: number;
  sanctioned: Money;
  spent: Money;
  ucs_due_30_days: number;
}

/** GET /reports/budget-vs-spend: allocated, committed and spent per budget head for a financial year, with grant totals. */
export interface BudgetVsSpendReport {
  /** e.g. 2026-27. */
  financial_year: string;
  allocated: Money;
  committed: Money;
  spent: Money;
  by_head: BudgetHeadSpend[];
  grants: GrantTotals;
}

export type BudgetVsSpendScope = "all" | "budgets" | "grants";

export interface BudgetVsSpendQuery {
  /** Defaults to the current financial year. */
  financial_year?: string;
  department_id?: string;
  /** Defaults to all. */
  scope?: BudgetVsSpendScope;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/budget-grants";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class BudgetGrantsApiError extends Error {
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
    throw new BudgetGrantsApiError(0, "The budget service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string | { message?: string } } | undefined;
    throw new BudgetGrantsApiError(res.status, body?.message ?? (typeof body?.detail === "string" ? body.detail : body?.detail?.message) ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** GET /me/grants. Permission budget-grants:self:read. */
export function getMyGrants(signal?: AbortSignal): Promise<MyGrant[]> {
  return get("/me/grants", {}, signal);
}

/** GET /reports/budget-vs-spend; the year defaults to the current financial year. Permission budget-grants:report:read. */
export function getBudgetVsSpend(query: BudgetVsSpendQuery = {}, signal?: AbortSignal): Promise<BudgetVsSpendReport> {
  return get("/reports/budget-vs-spend", { financial_year: query.financial_year, department_id: query.department_id, scope: query.scope }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof BudgetGrantsApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Budget data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load budget data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof BudgetGrantsApiError && (e.status === 401 || e.status === 403));
}
