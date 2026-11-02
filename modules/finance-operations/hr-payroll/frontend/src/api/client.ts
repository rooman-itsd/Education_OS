/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/hr-payroll) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is
 * replaced by the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** Money in the contract: a decimal string in rupees, e.g. "1500.00". Arithmetic on it is done in whole paise (see format.ts). */
export type Money = string;

/** components.schemas.LeaveStatus */
export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";

/** components.schemas.LeaveRequest, the fields the widget reads. */
export interface LeaveRequest {
  id: string;
  employee_id: string;
  employee_name: string;
  leave_type_id: string;
  leave_type_name: string;
  /** YYYY-MM-DD, both ends included. */
  from: string;
  to: string;
  /** Only when from equals to. */
  half_day?: "none" | "first_half" | "second_half";
  /** Calendar days, in halves. */
  days: number;
  /** False for an unpaid type: loss of pay. */
  paid: boolean;
  status: LeaveStatus;
  reason?: string;
  created_at: string;
}

/** components.schemas.LeaveRequestPage */
export interface LeaveRequestPage {
  items: LeaveRequest[];
  /** Pending requests matching every filter but status. */
  pending_total: number;
  next_cursor: string | null;
}

/** components.schemas.PayrollRun.status. computing and failed are not used while runs are computed in the request. */
export type PayrollRunStatus = "computing" | "review" | "submitted" | "approved" | "paid" | "failed";

/** components.schemas.PayrollRun, the fields the widget reads. */
export interface PayrollRun {
  id: string;
  /** Month, YYYY-MM. */
  period: string;
  status: PayrollRunStatus;
  employees: number;
  gross_total: Money;
  deductions_total: Money;
  net_total: Money;
  /** e.g. missing salary or bank account. */
  exceptions: { employee_id: string; message: string }[];
  /** Who submitted it last (who started it until then). */
  prepared_by: string;
  approved_by: string | null;
  /** The approver's note; why it was returned. */
  note: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  /** YYYY-MM-DD. */
  paid_on: string | null;
  bank_reference: string | null;
  /** YYYY-MM-DD: the payroll due day of the month. */
  due_on: string;
  /** Not yet approved and today is after due_on. */
  late: boolean;
  updated_at: string;
}

/** components.schemas.PersonEntry */
export interface PersonEntry {
  employee_id: string;
  name: string;
  designation?: string;
  department_name?: string | null;
  /** YYYY-MM-DD: the joining date, or the last working day. */
  date: string;
}

/** components.schemas.JoiningsAndExitsReport */
export interface JoiningsAndExitsReport {
  /** YYYY-MM-DD; defaults to the first day of the to date's month. */
  from: string;
  /** YYYY-MM-DD; defaults to today. */
  to: string;
  joined: number;
  /** Last working days in the range, up to today. */
  exited: number;
  /** Employees on the rolls on the to date. */
  headcount: number;
  /** Up to ten, latest first. */
  recent_joinings: PersonEntry[];
  /** Up to ten, latest first. */
  recent_exits: PersonEntry[];
  /** On notice, by last working day, up to ten. */
  upcoming_exits: PersonEntry[];
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/hr-payroll";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/**
 * A failed call. `status` is the HTTP status, or 0 when the service could not be reached. `code` is the contract's
 * error code ({"detail": {"code", "message"}}); a gateway or an unmounted module answers without one.
 */
export class HrPayrollApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
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

type ErrorBody = { code?: string; message?: string; detail?: string | { code?: string; message?: string } };

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
    throw new HrPayrollApiError(0, "The HR service could not be reached.");
  }
  if (!res.ok) {
    // {"detail": {"code", "message"}} from the contract; {"detail": "Not Found"} from the gateway or an unmounted module.
    const body = (await res.json().catch(() => undefined)) as ErrorBody | undefined;
    const detail = typeof body?.detail === "object" ? body.detail : undefined;
    const message = detail?.message ?? body?.message ?? (typeof body?.detail === "string" ? body.detail : undefined) ?? res.statusText;
    throw new HrPayrollApiError(res.status, message, detail?.code ?? body?.code);
  }
  return (await res.json()) as T;
}

/**
 * GET /leave-requests?status=pending: pending requests, soonest first, with the pending total.
 * Permission hr-payroll:leave:approve.
 */
export function getPendingLeaveRequests(signal?: AbortSignal): Promise<LeaveRequestPage> {
  return get("/leave-requests", { status: "pending" }, signal);
}

/**
 * GET /payroll-runs/current: the run for the current month, or the latest one. Permission hr-payroll:payroll:read.
 * The contract answers 404 `not_found` when there is no run yet; for the widget that is "no run", not a failure,
 * so it becomes null. A 404 without that code (the module is not mounted) stays an error.
 */
export async function getCurrentPayrollRun(signal?: AbortSignal): Promise<PayrollRun | null> {
  try {
    return await get<PayrollRun>("/payroll-runs/current", {}, signal);
  } catch (e) {
    if (e instanceof HrPayrollApiError && e.status === 404 && e.code === "not_found") return null;
    throw e;
  }
}

/**
 * GET /reports/joinings-and-exits: joinings and exits from the first of this month to today, with recent names and
 * upcoming last working days. Permission hr-payroll:report:read.
 */
export function getJoiningsAndExits(signal?: AbortSignal): Promise<JoiningsAndExitsReport> {
  return get("/reports/joinings-and-exits", {}, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof HrPayrollApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "HR data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load HR data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof HrPayrollApiError && (e.status === 401 || e.status === 403));
}
