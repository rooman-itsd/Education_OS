/**
 * Typed client for the parts of contracts/openapi.yaml the field-training frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type OpeningStatus = "draft" | "open" | "closed" | "cancelled";
export type PlacementStatus = "requested" | "assigned" | "active" | "completed" | "rejected" | "withdrawn";

export interface Opening {
  id: string;
  organisation_id: string;
  site_id: string;
  site_name?: string | null;
  title: string;
  discipline?: string | null;
  starts_on: string;
  ends_on: string;
  seats: number;
  seats_filled: number;
  required_hours?: number;
  allow_applications?: boolean;
  eligibility?: string | null;
  supervisor_ids?: string[];
  status: OpeningStatus;
}

export interface Placement {
  id: string;
  organisation_id: string;
  opening_id: string;
  opening_title?: string | null;
  site_id: string;
  site_name?: string | null;
  trainee_id: string;
  trainee_name?: string | null;
  supervisor_id?: string | null;
  supervisor_name?: string | null;
  starts_on: string;
  ends_on: string;
  status: PlacementStatus;
  statement?: string | null;
  required_hours?: number;
  verified_hours?: number;
  pending_hours?: number;
  final_outcome?: string | null;
  reason?: string | null;
}

export interface Page<T> {
  items: T[];
  next_cursor?: string | null;
}

export interface HoursSummary {
  /** Null when the caller has no placement. */
  placement_id: string | null;
  required_hours: number;
  verified_hours: number;
  pending_hours: number;
  returned_hours: number;
  by_date: { date: string; verified_hours: number; pending_hours: number }[];
}

export interface TraineeToAssess {
  placement: Placement;
  entries_awaiting: number;
  final_assessment_due: boolean;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class FieldTrainingApiError extends Error {
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
  const res = await fetch(`${API_BASE}/field-training${path}`, { headers, signal });
  if (!res.ok) throw new FieldTrainingApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
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
  if (!(e instanceof FieldTrainingApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Field training data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

/** GET /me/placements: the caller's placements, active first, then upcoming, then requested. Permission field-training:self:read. */
export function getMyPlacements(signal?: AbortSignal): Promise<Placement[]> {
  return get<Placement[]>("/me/placements", signal);
}

/** GET /me/hours: required, verified, awaiting and returned hours of the active or most recent placement. Permission field-training:self:read. */
export function getMyHours(signal?: AbortSignal): Promise<HoursSummary> {
  return get<HoursSummary>("/me/hours", signal);
}

/** GET /me/trainees: active placements the caller supervises that need action, most urgent first. Permission field-training:supervision:read. */
export function getMyTrainees(limit = 5, signal?: AbortSignal): Promise<TraineeToAssess[]> {
  return get<TraineeToAssess[]>(`/me/trainees?limit=${limit}`, signal);
}

/** GET /openings?status=open&has_seats=true: open openings with seats left. Permission field-training:opening:read. */
export function getOpenOpenings(limit = 5, signal?: AbortSignal): Promise<Page<Opening>> {
  return get<Page<Opening>>(`/openings?status=open&has_seats=true&limit=${limit}`, signal);
}

/** GET /placements?status=active: placements under way. Permission field-training:placement:read. */
export function getActivePlacements(limit = 5, signal?: AbortSignal): Promise<Page<Placement>> {
  return get<Page<Placement>>(`/placements?status=active&limit=${limit}`, signal);
}
