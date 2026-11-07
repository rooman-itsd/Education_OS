/**
 * Typed client for the parts of contracts/openapi.yaml the timetable-attendance widgets use. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the types
 * below must keep matching the contract's schemas (ScheduledClass, AttendanceToMarkItem, StudentAttendanceSummary,
 * DepartmentAttendanceReport).
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

export type ClassStatus = "scheduled" | "cancelled" | "completed";
export type SessionStatus = "open" | "closed" | "cancelled";

/** One class occurrence (components.schemas.ScheduledClass), the fields the widgets read. */
export interface ScheduledClass {
  id: string;
  course_offering_id: string;
  section_id: string;
  instructor_id: string;
  course_code?: string;
  course_title?: string;
  section_code?: string;
  class_date: string;
  starts_at: string;
  ends_at: string;
  location_label?: string | null;
  status: ClassStatus;
  cancel_reason?: string | null;
  attendance_session?: { id: string; status: SessionStatus } | null;
}

export interface DaySchedule {
  date: string;
  items: ScheduledClass[];
}

export interface AttendanceCounts {
  eligible: number;
  unmarked: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
}

/** A class the caller still has to mark (components.schemas.AttendanceToMarkItem). */
export interface AttendanceToMarkItem {
  scheduled_class: ScheduledClass;
  marking_deadline: string;
  counts?: AttendanceCounts;
}

/** One course offering of a student's summary (components.schemas.OfferingAttendance). */
export interface OfferingAttendance {
  course_offering_id: string;
  course_code?: string;
  course_title?: string;
  section_id?: string;
  classes_held: number;
  attended: number;
  excused: number;
  /** Null when no class was counted (every one excused). */
  percentage: number | null;
  below_threshold: boolean;
}

export interface StudentAttendanceSummary {
  student_id: string;
  academic_period_id: string;
  threshold_percent: number;
  overall_percentage?: number | null;
  items: OfferingAttendance[];
}

export interface DepartmentAttendanceRow {
  course_offering_id: string;
  course_code?: string;
  course_title?: string;
  section_id: string;
  section_code?: string;
  instructor_id?: string;
  classes_held: number;
  average_percentage: number | null;
  students_below_threshold: number;
}

export interface DepartmentAttendanceReport {
  department_id: string;
  academic_period_id: string;
  threshold_percent: number;
  overall_percentage?: number | null;
  items: DepartmentAttendanceRow[];
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

/** A refused request, with the contract's error `code` when the body carries one. */
export class TimetableAttendanceApiError extends Error {
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

async function errorCode(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: { code?: unknown } | string | null } | null;
    const detail = body?.detail;
    const code = typeof detail === "object" && detail !== null ? detail.code : undefined;
    return typeof code === "string" ? code : undefined;
  } catch {
    return undefined;
  }
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}/timetable-attendance${path}`, { headers, signal });
  if (!res.ok) throw new TimetableAttendanceApiError(res.status, res.statusText || `HTTP ${res.status}`, await errorCode(res));
  return (await res.json()) as T;
}

export interface Failure {
  title: string;
  detail?: string;
  retry: boolean;
}

export const UNAVAILABLE = "Timetable and attendance are not available yet.";
/** The department report needs the caller's department, which the platform cannot tell modules yet (PRD Q9). */
export const DEPARTMENT_UNKNOWN = "Your department is not known yet, so its attendance cannot be shown.";

/**
 * What a widget's error state says, as the other modules' widgets do. A missing or unreachable service (404 without a
 * code, 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof TimetableAttendanceApiError) || [404, 502, 503].includes(e.status)) {
    return { title: UNAVAILABLE, retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403 && e.code === "department_unknown") return { title: DEPARTMENT_UNKNOWN, retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

/** The viewer's own calendar date, YYYY-MM-DD: "today" is the viewer's, since the organisation's time zone has no source yet. */
export function localDate(now: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** GET /me/schedule: the classes of the caller's sections on a date. Permission scheduled-class:read-own. */
export function getMySchedule(date: string, signal?: AbortSignal): Promise<DaySchedule> {
  return get<DaySchedule>(`/me/schedule?date=${date}`, signal);
}

/** GET /me/teaching-schedule: the classes the caller teaches on a date. Permission scheduled-class:read. */
export function getMyTeachingSchedule(date: string, signal?: AbortSignal): Promise<DaySchedule> {
  return get<DaySchedule>(`/me/teaching-schedule?date=${date}`, signal);
}

/** GET /me/attendance-to-mark: the caller's classes still waiting for attendance, oldest first. Permission attendance-record:mark. */
export function getMyAttendanceToMark(signal?: AbortSignal): Promise<{ items: AttendanceToMarkItem[]; total: number }> {
  return get<{ items: AttendanceToMarkItem[]; total: number }>("/me/attendance-to-mark", signal);
}

/**
 * GET /me/attendance-summary for the active term. Permission report:read-own. With no active term the API answers 404
 * `active_term_not_found`, which is "nothing to show yet": this returns null then.
 */
export async function getMyAttendanceSummary(signal?: AbortSignal): Promise<StudentAttendanceSummary | null> {
  try {
    return await get<StudentAttendanceSummary>("/me/attendance-summary", signal);
  } catch (e) {
    if (e instanceof TimetableAttendanceApiError && e.status === 404 && e.code === "active_term_not_found") return null;
    throw e;
  }
}

/**
 * GET /reports/department-attendance for the caller's department and the active term. Permission
 * report:read-department. Null when no term is active (404 `active_term_not_found`).
 */
export async function getDepartmentAttendance(signal?: AbortSignal): Promise<DepartmentAttendanceReport | null> {
  try {
    return await get<DepartmentAttendanceReport>("/reports/department-attendance", signal);
  } catch (e) {
    if (e instanceof TimetableAttendanceApiError && e.status === 404 && e.code === "active_term_not_found") return null;
    throw e;
  }
}
