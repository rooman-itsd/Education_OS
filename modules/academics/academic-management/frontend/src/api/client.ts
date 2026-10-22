/**
 * Typed client for the parts of contracts/openapi.yaml the academic-management frontend uses. The repo has no
 * OpenAPI generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas (MyOffering, RosterEntry).
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

export type FacultyRole = "primary" | "co_instructor" | "teaching_assistant";
export type OfferingStatus = "planned" | "open" | "in_progress" | "completed" | "cancelled";

export interface CourseSummary {
  code: string;
  title: string;
  credits: number;
  course_type: string;
  department_id?: string;
}

/** components.schemas.MyOffering */
export interface MyOffering {
  course_offering_id: string;
  course: CourseSummary;
  role: FacultyRole;
  status?: OfferingStatus;
  /** The sections the caller teaches (every section when assigned to the whole offering). */
  sections: { section_id: string; code: string; enrolled_count: number }[];
  enrolled_count: number;
}

/** GET /me/offerings */
export interface MyOfferings {
  academic_period_id: string | null;
  items: MyOffering[];
}

/** components.schemas.RosterEntry */
export interface RosterEntry {
  person_id: string;
  student_name?: string;
  roll_number?: string;
  section_id: string;
  section_code?: string;
  enrolled_at: string;
}

/** GET /offerings/{course_offering_id}/roster */
export interface RosterPage {
  course_offering_id: string;
  items: RosterEntry[];
  total: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class AcademicManagementApiError extends Error {
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
  const res = await fetch(`${API_BASE}/academic-management${path}`, { headers, signal });
  if (!res.ok) throw new AcademicManagementApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /me/offerings: the offerings the caller teaches in the active term. Permission academic-management:roster:read. */
export function getMyOfferings(signal?: AbortSignal): Promise<MyOfferings> {
  return get<MyOfferings>("/me/offerings", signal);
}

/** GET /offerings/{id}/roster: the enrolled learners of one offering the caller teaches. */
export function getRoster(courseOfferingId: string, limit = 200, signal?: AbortSignal): Promise<RosterPage> {
  return get<RosterPage>(`/offerings/${encodeURIComponent(courseOfferingId)}/roster?limit=${limit}`, signal);
}
