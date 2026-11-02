/**
 * Typed client for platform/reporting API.
 */

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class ReportingApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ReportingApiError";
  }
}

function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (options.body && typeof options.body === "string") headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) throw new ReportingApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface ReportDefinition {
  id: string;
  organisation_id: string;
  code: string;
  name: string;
  description?: string | null;
  category: string;
  parameters_schema?: Record<string, unknown> | null;
  is_system: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReportExecution {
  id: string;
  organisation_id: string;
  report_definition_id: string;
  requested_by: string;
  status: "pending" | "completed" | "failed" | string;
  parameters?: Record<string, unknown> | null;
  result_summary?: Record<string, unknown> | null;
  export_file_id?: string | null;
  error_message?: string | null;
  client_token?: string | null;
  executed_at: string;
  completed_at?: string | null;
}

export interface ExportResponse {
  download_url: string;
  filename: string;
  format: string;
  expires_in_seconds: number;
}

export interface DepartmentReportsWidgetData {
  department_id: string;
  department_name: string;
  attendance_rate: number;
  exam_pass_rate: number;
  faculty_load_average: number;
  recent_reports: Array<{
    id: string;
    code: string;
    title: string;
    generated_at: string;
  }>;
}

export interface AttendanceAndResultsWidgetData {
  institution_average_attendance: number;
  institution_average_pass_rate: number;
  departments: Array<{
    department_id: string;
    department_name: string;
    attendance_rate: number;
    pass_rate: number;
    total_students: number;
    is_attendance_low: boolean;
  }>;
}

export interface Failure {
  title: string;
  detail?: string;
  retry: boolean;
}

export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof ReportingApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Reporting service is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to continue.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this report.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export const listDefinitions = (params?: { category?: string; is_active?: boolean }, signal?: AbortSignal) => {
  const q = new URLSearchParams();
  if (params?.category) q.set("category", params.category);
  if (params?.is_active !== undefined) q.set("is_active", String(params.is_active));
  const qs = q.toString();
  return request<ReportDefinition[]>(`/reporting/definitions${qs ? `?${qs}` : ""}`, { signal });
};

export const getDefinition = (id: string, signal?: AbortSignal) =>
  request<ReportDefinition>(`/reporting/definitions/${id}`, { signal });

export const createDefinition = (input: { code: string; name: string; category: string; description?: string; parameters_schema?: Record<string, unknown> }, signal?: AbortSignal) =>
  request<ReportDefinition>("/reporting/definitions", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });

export const updateDefinition = (id: string, input: { name?: string; description?: string; category?: string; parameters_schema?: Record<string, unknown>; is_active?: boolean }, signal?: AbortSignal) =>
  request<ReportDefinition>(`/reporting/definitions/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
    signal,
  });

export const runReport = (id: string, input?: { parameters?: Record<string, unknown>; client_token?: string }, signal?: AbortSignal) =>
  request<ReportExecution>(`/reporting/definitions/${id}/run`, {
    method: "POST",
    body: input ? JSON.stringify(input) : undefined,
    signal,
  });

export const getExecution = (id: string, signal?: AbortSignal) =>
  request<ReportExecution>(`/reporting/executions/${id}`, { signal });

export const exportReport = (id: string, format: "csv" | "json" = "csv", signal?: AbortSignal) =>
  request<ExportResponse>(`/reporting/executions/${id}/export?format=${format}`, { signal });

export const getDepartmentReportsWidget = (departmentId?: string, signal?: AbortSignal) => {
  const qs = departmentId ? `?department_id=${encodeURIComponent(departmentId)}` : "";
  return request<DepartmentReportsWidgetData>(`/reporting/widgets/department-reports${qs}`, { signal });
};

export const getAttendanceAndResultsWidget = (signal?: AbortSignal) =>
  request<AttendanceAndResultsWidgetData>("/reporting/widgets/attendance-and-results", { signal });

