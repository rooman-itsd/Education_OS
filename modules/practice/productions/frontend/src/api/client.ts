/**
 * Typed client for the parts of contracts/openapi.yaml the productions frontend uses. The repo has no
 * OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the generated client and
 * the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

/** contract Kind */
export type Kind =
  | "performance"
  | "exhibition"
  | "recital"
  | "screening"
  | "hackathon"
  | "competition"
  | "conference"
  | "other";

/** contract Status */
export type Status = "planned" | "in_preparation" | "scheduled" | "completed" | "cancelled";

/** contract RoleKind and RoleStatus */
export type RoleKind = "cast" | "crew" | "mentor";
export type RoleStatus = "invited" | "confirmed" | "declined" | "withdrawn";

/** contract CalendarEntry */
export interface CalendarEntry {
  id: string;
  title: string;
  kind: Kind;
  status: Status;
  department?: string | null;
  venue?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
  call_time?: string | null;
  cast_confirmed: number;
}

/** contract MyRole */
export interface MyRole {
  role_id: string;
  production_id: string;
  role_name: string;
  role_kind: RoleKind;
  role_status: RoleStatus;
  title: string;
  kind: Kind;
  status: Status;
  venue?: string | null;
  starts_at?: string | null;
  call_time?: string | null;
}

/** contract PreparationEntry */
export interface PreparationEntry {
  id: string;
  title: string;
  kind: Kind;
  status: Status;
  department?: string | null;
  starts_at?: string | null;
  lead_user_id: string;
  tasks_open: number;
  tasks_total: number;
  tasks_overdue: number;
  next_task_due_at?: string | null;
  cast_unanswered: number;
}

/** contract CalendarPage / MyRolePage / PreparationPage */
export interface Page<T> {
  items: T[];
  /** How many match in all, not only the ones returned. */
  total: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class ProductionsApiError extends Error {
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
  const res = await fetch(`${API_BASE}/productions${path}`, { headers, signal });
  if (!res.ok) throw new ProductionsApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined) search.set(key, String(value));
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

/** GET /calendar: what is on in a window, soonest first. Permission productions:production:read. */
export function getCalendar(
  options: { from?: string; to?: string; limit?: number } = {},
  signal?: AbortSignal,
): Promise<Page<CalendarEntry>> {
  return get<Page<CalendarEntry>>(`/calendar${query(options)}`, signal);
}

/** GET /upcoming: the next scheduled productions. Permission productions:production:read. */
export function getUpcoming(options: { limit?: number } = {}, signal?: AbortSignal): Promise<Page<CalendarEntry>> {
  return get<Page<CalendarEntry>>(`/upcoming${query(options)}`, signal);
}

/** GET /my-roles: the caller's own parts. Permission productions:role:read-own. */
export function getMyRoles(
  options: { open?: boolean; limit?: number } = {},
  signal?: AbortSignal,
): Promise<Page<MyRole>> {
  return get<Page<MyRole>>(`/my-roles${query(options)}`, signal);
}

/** GET /in-preparation: what is being got ready. Permission productions:task:read. */
export function getInPreparation(
  options: { mine?: boolean; limit?: number } = {},
  signal?: AbortSignal,
): Promise<Page<PreparationEntry>> {
  return get<Page<PreparationEntry>>(`/in-preparation${query(options)}`, signal);
}

/** What each kind is called on screen. The profile vocabulary renames productions; the kind stays neutral. */
export const KIND_LABEL: Record<Kind, string> = {
  performance: "Performance",
  exhibition: "Exhibition",
  recital: "Recital",
  screening: "Screening",
  hackathon: "Hackathon",
  competition: "Competition",
  conference: "Conference",
  other: "Production",
};

/** "30 Oct"; "—" when the value is missing or not a date (Date gives "Invalid Date" instead of throwing). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** "19:30", in the viewer's own time zone; "" when there is nothing to show. */
export function shortTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

/** "2026-11-30" for the date tile of a row, or undefined when the production has no date yet. */
export function dateTile(iso: string | null | undefined): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  const month = String(d.getMonth() + 1).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${String(d.getDate()).padStart(2, "0")}`;
}

/** "Main Hall · 19:30", leaving out whichever part is missing. */
export function placeAndTime(entry: { venue?: string | null; starts_at?: string | null }): string {
  return [entry.venue ?? "", shortTime(entry.starts_at)].filter(Boolean).join(" · ");
}

export interface Failure {
  title: string;
  detail?: string;
  retry: boolean;
}

/**
 * What a widget's error state says, as the other modules' widgets do. A missing or unreachable service (404,
 * 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof ProductionsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Production data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}
