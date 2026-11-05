/**
 * Typed client for the parts of contracts/openapi.yaml the skill-progress frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types
 * below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** contract SkillProficiencyStatus */
export interface SkillProficiencyStatus {
  skill_id: string;
  skill_title: string;
  category?: string | null;
  latest_score: number;
  latest_level: string;
  total_evaluations?: number;
  latest_assessed_at: string;
}

/** contract LearnerProgressSummary */
export interface LearnerProgressSummary {
  learner_id: string;
  organisation_id: string;
  skills_evaluated: number;
  current_skills: SkillProficiencyStatus[];
}

/** contract AssessmentRecord, the fields the widgets read */
export interface Assessment {
  id: string;
  learner_id: string;
  evaluator_id: string;
  skill_id: string;
  assessed_at: string;
  overall_score: number;
  level_achieved: string;
  status?: "submitted" | "verified" | "voided";
}

/** contract Skill, the fields the widgets read */
export interface Skill {
  id: string;
  title: string;
}

/** The list shape of GET /assessments and GET /skills */
export interface Page<T> {
  items: T[];
  total: number;
}

/** contract FrameworkSummaryReport */
export interface FrameworkSummary {
  framework_id: string;
  framework_title: string;
  learners_assessed: number;
  levels: { level: string; count: number }[];
}
export interface FrameworkSummaryReport {
  items: FrameworkSummary[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class SkillProgressApiError extends Error {
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
  const res = await fetch(`${API_BASE}/skill-progress${path}`, { headers, signal });
  if (!res.ok) throw new SkillProgressApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /me/progress: the caller's latest level on every skill they were assessed on. Permission skill-progress:progress:read. */
export function getMyProgress(signal?: AbortSignal): Promise<LearnerProgressSummary> {
  return get<LearnerProgressSummary>("/me/progress", signal);
}

/** GET /assessments?status=submitted: recorded and waiting for verification, newest first. Permission skill-progress:assessment:read. */
export function listAssessmentsToVerify(limit: number, signal?: AbortSignal): Promise<Page<Assessment>> {
  return get<Page<Assessment>>(`/assessments?status=submitted&limit=${limit}`, signal);
}

/** GET /skills: the titles the assessments refer to. Permission skill-progress:framework:read. */
export function listSkills(signal?: AbortSignal): Promise<Page<Skill>> {
  return get<Page<Skill>>("/skills?limit=100", signal);
}

/** GET /reports/framework-summary: learners assessed and skills at each level, per framework. Permission skill-progress:progress:read. */
export function getFrameworkSummary(signal?: AbortSignal): Promise<FrameworkSummaryReport> {
  return get<FrameworkSummaryReport>("/reports/framework-summary", signal);
}

/** "12 Oct"; "—" when the value is missing or not a date. */
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
  if (!(e instanceof SkillProgressApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Skill progress data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}
