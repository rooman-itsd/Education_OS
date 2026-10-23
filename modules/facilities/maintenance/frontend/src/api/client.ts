/**
 * Typed client for the parts of contracts/openapi.yaml the maintenance frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type Priority = "low" | "medium" | "high" | "urgent";
export type TicketStatus = "open" | "assigned" | "in_progress" | "on_hold" | "resolved" | "closed" | "cancelled";

/** contract Target */
export interface Target {
  kind: "asset" | "resource" | "unit" | "location";
  id?: string;
  label: string;
}

/** contract Ticket, the fields the widget reads */
export interface Ticket {
  id: string;
  number: string;
  kind: "corrective" | "preventive" | "inspection";
  title: string;
  category_name?: string;
  target: Target;
  priority: Priority;
  status: TicketStatus;
  blocks_use: boolean;
  assignee_id?: string | null;
  vendor?: { name: string } | null;
  sla_breached: ("response" | "resolution")[];
  resolution_due_at?: string;
}

/** contract TicketPage */
export interface TicketPage {
  items: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

/** contract Summary */
export interface Summary {
  open: number;
  unassigned: number;
  in_progress: number;
  on_hold: number;
  urgent_open: number;
  sla_breached_open: number;
  resolved_awaiting_confirmation: number;
  preventive_due_7_days: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class MaintenanceApiError extends Error {
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
  const res = await fetch(`${API_BASE}/maintenance${path}`, { headers, signal });
  if (!res.ok) throw new MaintenanceApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/**
 * GET /tickets?scope=managed&open=true: every open ticket in the organisation, SLA-breached first, then urgent.
 * Permission maintenance:ticket:read with maintenance:ticket:read-all.
 */
export function listOpenTickets(pageSize: number, signal?: AbortSignal): Promise<TicketPage> {
  return get<TicketPage>(`/tickets?scope=managed&open=true&page_size=${pageSize}`, signal);
}

/** GET /summary: counts for the tickets widget. Permission maintenance:ticket:read. */
export function getSummary(signal?: AbortSignal): Promise<Summary> {
  return get<Summary>("/summary", signal);
}
