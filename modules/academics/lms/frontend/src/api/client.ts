/**
 * Typed client for the parts of contracts/openapi.yaml the lms frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas (GradingQueueItem, RecentMaterialItem).
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type ItemType = "assignment" | "quiz";
export type MaterialType = "document" | "link" | "page";

/** One assignment or quiz with work waiting for a grade (GET /me/grading-queue). */
export interface GradingQueueItem {
  course_space_id: string;
  course_title?: string;
  item_type: ItemType;
  item_id: string;
  title: string;
  due_at?: string | null;
  /** Ungraded submissions, or quiz attempts waiting for essay scores. */
  waiting_count: number;
  oldest_waiting_since: string;
}

export interface GradingQueue {
  items: GradingQueueItem[];
  total: number;
}

/** A recently published material in one of the caller's course spaces (GET /me/course-materials). */
export interface RecentMaterialItem {
  material_id: string;
  course_space_id: string;
  course_title?: string;
  title: string;
  material_type: MaterialType;
  published_at: string;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class LmsApiError extends Error {
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
  const res = await fetch(`${API_BASE}/lms${path}`, { headers, signal });
  if (!res.ok) throw new LmsApiError(res.status, res.statusText || `HTTP ${res.status}`);
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
  if (!(e instanceof LmsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Course data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

/** GET /me/grading-queue: work waiting for a grade in the course spaces the caller teaches, oldest first. Permission lms:grade:manage-assigned. */
export function getMyGradingQueue(signal?: AbortSignal): Promise<GradingQueue> {
  return get<GradingQueue>("/me/grading-queue", signal);
}

/** GET /me/course-materials: recently published materials in the caller's course spaces, newest first. Permission lms:course-space:read-own. */
export function getMyCourseMaterials(limit = 5, signal?: AbortSignal): Promise<{ items: RecentMaterialItem[] }> {
  return get<{ items: RecentMaterialItem[] }>(`/me/course-materials?limit=${limit}`, signal);
}
