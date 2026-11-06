/**
 * Typed client for the parts of contracts/openapi.yaml the projects frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type ProjectStatus = "proposed" | "active" | "submitted" | "completed" | "rejected" | "cancelled";
export type MilestoneStatus = "pending" | "submitted" | "accepted" | "returned" | "cancelled";

export interface Project {
  id: string;
  organisation_id: string;
  title: string;
  summary?: string;
  kind?: string;
  academic_year?: string;
  starts_on?: string;
  ends_on?: string;
  external_partner?: string | null;
  status: ProjectStatus;
  lead_id?: string | null;
  guide_ids?: string[];
  member_count?: number;
  milestones_total?: number;
  milestones_accepted?: number;
  outcome?: string | null;
  score?: number | null;
  reason?: string | null;
}

export interface ProjectPage {
  items: Project[];
  next_cursor?: string | null;
}

export interface Milestone {
  id: string;
  organisation_id: string;
  project_id: string;
  title: string;
  description?: string;
  due_on: string;
  weight?: number | null;
  status: MilestoneStatus;
  overdue?: boolean;
  latest_submission_at?: string | null;
}

export interface MyProject extends Project {
  my_role?: "lead" | "member";
  next_milestone?: Milestone | null;
}

export interface MilestoneDue extends Milestone {
  project_title: string;
  /** Negative when overdue. */
  days_left?: number;
}

export interface Submission {
  id: string;
  organisation_id: string;
  project_id: string;
  milestone_id?: string | null;
  version: number;
  note: string;
  document_ids?: string[];
  submitted_by: string;
  submitted_at: string;
}

export interface ReviewItem {
  kind: "milestone" | "final";
  project_id: string;
  project_title: string;
  milestone_id?: string | null;
  milestone_title?: string | null;
  submission: Submission;
  waiting_days?: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class ProjectsApiError extends Error {
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
  const res = await fetch(`${API_BASE}/projects${path}`, { headers, signal });
  if (!res.ok) throw new ProjectsApiError(res.status, res.statusText || `HTTP ${res.status}`);
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
  if (!(e instanceof ProjectsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Projects data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

/** GET /me/projects: the caller's projects, in progress first, with progress and the next milestone. Permission projects:self:read. */
export function getMyProjects(signal?: AbortSignal): Promise<MyProject[]> {
  return get<MyProject[]>("/me/projects", signal);
}

/** GET /me/milestones: pending, returned and overdue milestones of the caller's active projects, earliest first. Permission projects:self:read. */
export function getMyMilestones(withinDays = 14, signal?: AbortSignal): Promise<MilestoneDue[]> {
  return get<MilestoneDue[]>(`/me/milestones?within_days=${withinDays}`, signal);
}

/** GET /me/reviews: submitted milestones and projects awaiting the caller as guide, oldest first. Permission projects:guidance:read. */
export function getMyReviews(limit = 5, signal?: AbortSignal): Promise<ReviewItem[]> {
  return get<ReviewItem[]>(`/me/reviews?limit=${limit}`, signal);
}

/**
 * GET /projects?status=active: active projects. With only projects:guidance:read the caller sees the projects they
 * guide; with projects:project:read every project.
 */
export function getActiveProjects(limit = 5, signal?: AbortSignal): Promise<ProjectPage> {
  return get<ProjectPage>(`/projects?status=active&limit=${limit}`, signal);
}
