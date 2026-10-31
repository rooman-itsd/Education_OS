/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/sports-nutrition-health) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by
 * the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 *
 * Athletes are referenced by id only (athlete-performance owns their names); this module has no endpoint that
 * names them, and a widget does not call another module's API.
 */

/** A page of a list endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
}

export type PlanStatus = "draft" | "active" | "completed" | "archived";
export type PlanGoal = "performance" | "weight_gain" | "weight_loss" | "recovery" | "maintenance";

/** contract NutritionPlan (the fields the widgets read). */
export interface NutritionPlan {
  id: string;
  athlete_id: string;
  nutritionist_id?: string;
  title: string;
  goal: PlanGoal;
  daily_calories?: number;
  protein_g?: number;
  carbohydrate_g?: number;
  fat_g?: number;
  meals?: { meal: string; items: string }[];
  /** YYYY-MM-DD */
  start_date: string;
  /** YYYY-MM-DD */
  end_date?: string;
  /** YYYY-MM-DD */
  review_due_on?: string;
  status: PlanStatus;
}

export type InjuryStatus = "active" | "recovering" | "resolved";
export type Severity = "minor" | "moderate" | "severe";

/**
 * contract Injury, without clinical_notes. The service returns the notes to callers with health-record:read
 * (medical staff), but no dashboard widget shows them, so the client drops them before a widget sees the row.
 */
export interface Injury {
  id: string;
  athlete_id: string;
  body_part: string;
  injury_type?: string;
  severity: Severity;
  /** YYYY-MM-DD */
  occurred_on: string;
  context?: "training" | "competition" | "other";
  status: InjuryStatus;
  /** YYYY-MM-DD */
  expected_return_on?: string;
}

export type AppointmentType = "physiotherapy" | "medical" | "nutrition";
export type AppointmentStatus = "scheduled" | "completed" | "cancelled" | "no_show";

/** contract Appointment (the fields the widgets read; the clinical `notes` are dropped like an injury's). */
export interface Appointment {
  id: string;
  athlete_id: string;
  practitioner_id: string;
  appointment_type: AppointmentType;
  injury_id?: string;
  /** date-time */
  scheduled_at: string;
  duration_minutes?: number;
  status: AppointmentStatus;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/sports-nutrition-health";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class SportsNutritionHealthApiError extends Error {
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

async function get<T>(path: string, query: Record<string, string | number | undefined> = {}, signal?: AbortSignal): Promise<T> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined) params.set(k, String(v));
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
    throw new SportsNutritionHealthApiError(0, "The sports nutrition and health service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string } | undefined;
    throw new SportsNutritionHealthApiError(res.status, body?.message ?? body?.detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

/**
 * GET /nutrition-plans. Athletes get only their own plans; staff get their organisation's. `review_due_before`
 * keeps plans whose review_due_on is on or before that day (and not completed or archived).
 * Permission sports-nutrition-health:plan:read.
 */
export function listNutritionPlans(
  query: { status?: PlanStatus; review_due_before?: string; limit: number },
  signal?: AbortSignal,
): Promise<Page<NutritionPlan>> {
  return get("/nutrition-plans", query, signal);
}

/** GET /injuries, newest first, clinical notes removed. Permission sports-nutrition-health:injury:read. */
export async function listInjuries(query: { status?: InjuryStatus; limit: number }, signal?: AbortSignal): Promise<Page<Injury>> {
  const page = await get<Page<Injury & { clinical_notes?: string }>>("/injuries", query, signal);
  return {
    total: page.total,
    items: page.items.map(({ clinical_notes: _notes, ...injury }) => injury),
  };
}

/**
 * GET /appointments, by scheduled time, clinical notes removed. `on` is a calendar day in UTC (the backend
 * compares scheduled_at with that day's UTC midnight to midnight). Permission sports-nutrition-health:appointment:read.
 */
export async function listAppointments(query: { on?: string; limit: number }, signal?: AbortSignal): Promise<Page<Appointment>> {
  const page = await get<Page<Appointment & { notes?: string }>>("/appointments", query, signal);
  return {
    total: page.total,
    items: page.items.map(({ notes: _notes, ...appointment }) => appointment),
  };
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof SportsNutritionHealthApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Nutrition and health data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load nutrition and health data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof SportsNutritionHealthApiError && (e.status === 401 || e.status === 403));
}
