/**
 * Typed client for the parts of contracts/openapi.yaml the inventory-equipment frontend uses. The repo has no
 * OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** contract LoanStatus */
export type LoanStatus =
  | "requested"
  | "approved"
  | "rejected"
  | "cancelled"
  | "on_loan"
  | "partially_returned"
  | "overdue"
  | "returned"
  | "closed_with_loss";

/** contract LowStockLine */
export interface LowStockLine {
  item_id: string;
  /** Null when the item was deleted after the loan was made. */
  item_name: string | null;
  category_id?: string;
  available: number;
  reorder_level: number;
  reorder_quantity?: number;
  unit_of_measure: string;
  low_since?: string;
}

/** contract LoanLine, the fields the widgets read */
export interface LoanLine {
  id: string;
  item_id: string;
  item_name: string;
  quantity: number;
  unit_id?: string | null;
  unit_tag?: string | null;
  status: "waiting" | "out" | "returned" | "lost";
}

/** contract Loan, the fields the widgets read */
export interface Loan {
  id: string;
  borrower_id: string;
  status: LoanStatus;
  lines: LoanLine[];
  purpose?: string;
  due_at: string;
  /** 0 when not overdue */
  days_overdue: number;
  created_at?: string;
}

/** contract LoanPage */
export interface LoanPage {
  items: Loan[];
  total: number;
  page: number;
  page_size: number;
}

export interface LoanQuery {
  scope?: "mine" | "managed";
  status?: LoanStatus[];
  open?: boolean;
  page_size?: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class InventoryApiError extends Error {
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
  const res = await fetch(`${API_BASE}/inventory-equipment${path}`, { headers, signal });
  if (!res.ok) throw new InventoryApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /low-stock: items at or below their reorder level, shortest first. Permission inventory-equipment:stock:read. */
export function getLowStock(signal?: AbortSignal): Promise<LowStockLine[]> {
  return get<LowStockLine[]>("/low-stock", signal);
}

/**
 * GET /loans: scope=mine (default) is the caller's loans; scope=managed is the loans the caller approves or, with
 * inventory-equipment:loan:read-all, every loan. Permission inventory-equipment:loan:read.
 */
export function listLoans(query: LoanQuery = {}, signal?: AbortSignal): Promise<LoanPage> {
  const params = new URLSearchParams();
  if (query.scope) params.set("scope", query.scope);
  if (query.status?.length) params.set("status", query.status.join(","));
  if (query.open !== undefined) params.set("open", String(query.open));
  if (query.page_size) params.set("page_size", String(query.page_size));
  const qs = params.toString();
  return get<LoanPage>(`/loans${qs ? `?${qs}` : ""}`, signal);
}

/** A quantity for display: no float noise ("10.200000000000001" is "10.2"), at most two decimals. */
export function qty(n: number): string {
  return Number.isFinite(n) ? n.toLocaleString("en-GB", { maximumFractionDigits: 2 }) : "—";
}

/** "Violin VN-03, Music stand × 2": what a loan holds, for one line of a widget row. */
export function loanItems(loan: Loan): string {
  return loan.lines
    .map((l) => {
      const name = l.item_name ?? "Item";
      return l.unit_tag ? `${name} ${l.unit_tag}` : l.quantity > 1 ? `${name} × ${qty(l.quantity)}` : name;
    })
    .join(", ");
}

/** "30 Oct"; "—" when the value is missing or not a date (Date gives "Invalid Date" instead of throwing). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
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
  if (!(e instanceof InventoryApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Inventory data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}
