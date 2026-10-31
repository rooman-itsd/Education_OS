/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/athlete-performance) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by
 * the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** A page of a list endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
}

export type MetricDirection = "higher_is_better" | "lower_is_better";

/** contract Metric: something measurable about performance or fitness, e.g. 100 m time (s) or body fat (%). */
export interface Metric {
  id: string;
  name: string;
  unit: string;
  direction: MetricDirection;
  /** Absent for metrics that belong to no discipline (fitness and body measurements). */
  discipline_id?: string;
}

/** contract FitnessTest: a battery of measurements taken together, e.g. a body composition check. */
export interface FitnessTest {
  id: string;
  name: string;
  metric_ids: string[];
  discipline_id?: string;
}

export type AthleteStatus = "active" | "inactive" | "alumni";

/** contract Athlete (the fields the widgets read). */
export interface Athlete {
  id: string;
  full_name: string;
  primary_discipline_id: string;
  discipline_ids?: string[];
  squad?: string;
  status: AthleteStatus;
}

/** contract PerformanceResult (the fields the widgets read). */
export interface PerformanceResult {
  id: string;
  athlete_id: string;
  metric_id: string;
  value: number;
  /** date-time */
  recorded_at: string;
  context: "training" | "trial" | "competition";
}

/** contract FitnessAssessment (the fields the widgets read). */
export interface FitnessAssessment {
  id: string;
  athlete_id: string;
  fitness_test_id: string;
  /** YYYY-MM-DD */
  assessed_on: string;
  measurements: { metric_id: string; value: number }[];
}

/** contract Benchmark (the fields the widgets read). */
export interface Benchmark {
  id: string;
  metric_id: string;
  level: string;
  target_value: number;
}

/** contract PerformanceHistory: results and assessment measurements over time, oldest first. */
export interface PerformanceHistory {
  athlete_id: string;
  metric_id: string;
  points: { at: string; value: number; source: "result" | "assessment" }[];
  benchmark?: Benchmark;
}

export type ClearanceStatus = "cleared" | "restricted" | "not_cleared";

/** contract FitnessClearance. `not_cleared` when none was recorded or once valid_until has passed. */
export interface FitnessClearance {
  athlete_id: string;
  status: ClearanceStatus;
  /** YYYY-MM-DD */
  valid_until?: string;
  restrictions?: string;
  set_at?: string;
}

/** contract ClearanceReportRow: an active athlete's clearance, with their name and whether it lapses soon. */
export interface ClearanceReportRow extends FitnessClearance {
  full_name: string;
  lapsing_soon: boolean;
}

/** GET /reports/clearances: most urgent first; counts cover every active athlete, not only the page. */
export interface ClearanceReport {
  items: ClearanceReportRow[];
  total: number;
  counts: { cleared: number; restricted: number; not_cleared: number; lapsing_soon: number };
}

export type Trend ="improving" | "steady" | "declining" | "no_data";

/** contract SquadSummaryRow: latest value and trend of every metric the athlete has values for. */
export interface SquadSummaryRow {
  athlete_id: string;
  full_name: string;
  clearance?: ClearanceStatus;
  metrics?: { metric_id?: string; latest_value?: number; trend?: Trend }[];
}

export interface SquadSummary {
  items: SquadSummaryRow[];
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/athlete-performance";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class AthletePerformanceApiError extends Error {
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
    throw new AthletePerformanceApiError(0, "The athlete performance service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string } | undefined;
    throw new AthletePerformanceApiError(res.status, body?.message ?? body?.detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** GET /reports/squad-summary: active athletes with each metric's latest value and trend. Permission athlete-performance:report:read. */
export function getSquadSummary(signal?: AbortSignal): Promise<SquadSummary> {
  return get("/reports/squad-summary", {}, signal);
}

/** GET /metrics (first page of 200, by name). Permission athlete-performance:catalogue:read. */
export function listMetrics(signal?: AbortSignal): Promise<Page<Metric>> {
  return get("/metrics", { limit: 200 }, signal);
}

/** GET /fitness-tests (first page of 200, by name). Permission athlete-performance:catalogue:read. */
export function listFitnessTests(signal?: AbortSignal): Promise<Page<FitnessTest>> {
  return get("/fitness-tests", { limit: 200 }, signal);
}

/**
 * GET /athletes, by name. Athletes get only their own profile; staff get their organisation's athletes.
 * Permission athlete-performance:athlete:read.
 */
export function listAthletes(query: { status?: AthleteStatus; limit: number }, signal?: AbortSignal): Promise<Page<Athlete>> {
  return get("/athletes", query, signal);
}

/** GET /results for one athlete, newest first. Permission athlete-performance:result:read. */
export function listResults(athleteId: string, limit: number, signal?: AbortSignal): Promise<Page<PerformanceResult>> {
  return get("/results", { athlete_id: athleteId, limit }, signal);
}

/** GET /assessments for one athlete, newest first. Permission athlete-performance:assessment:read. */
export function listAssessments(athleteId: string, limit: number, signal?: AbortSignal): Promise<Page<FitnessAssessment>> {
  return get("/assessments", { athlete_id: athleteId, limit }, signal);
}

/** GET /athletes/{id}/history for one metric. Permission athlete-performance:result:read. */
export function getPerformanceHistory(athleteId: string, metricId: string, signal?: AbortSignal): Promise<PerformanceHistory> {
  return get(`/athletes/${encodeURIComponent(athleteId)}/history`, { metric_id: metricId }, signal);
}

/** GET /reports/clearances: every active athlete's clearance, most urgent first. Permission athlete-performance:clearance:read. */
export function getClearanceReport(
  query: { lapsing_within_days: number; limit: number },
  signal?: AbortSignal,
): Promise<ClearanceReport> {
  return get("/reports/clearances", query, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof AthletePerformanceApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Athlete performance data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load athlete performance data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof AthletePerformanceApiError && (e.status === 401 || e.status === 403));
}
