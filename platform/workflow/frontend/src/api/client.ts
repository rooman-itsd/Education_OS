/**
 * Typed client for platform/workflow API.
 */

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class WorkflowApiError extends Error {
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

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (options.body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) throw new WorkflowApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

export interface Failure {
  title: string;
  detail?: string;
  retry: boolean;
}

export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof WorkflowApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Workflow data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export function humanise(id: string): string {
  const words = id.replace(/[-_.]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : id;
}

export interface WorkflowRequest {
  id: string;
  organisation_id: string;
  chain_id: string;
  entity_type: string;
  entity_id: string;
  title: string;
  description?: string;
  requester_id: string;
  requester_name?: string;
  current_step_order: number;
  status: string;
  submitted_at: string;
  completed_at?: string;
  current_step_deadline?: string;
  is_overdue: boolean;
  delegated_to?: string;
  client_token?: string;
  context: Record<string, unknown>;
}

export interface RequestPage {
  items: WorkflowRequest[];
  total: number;
}

export const pendingRequests = (limit: number, signal?: AbortSignal) =>
  request<RequestPage>(`/workflow/requests/pending?limit=${limit}`, { signal });

export const approveRequest = (id: string, comments?: string) =>
  request<WorkflowRequest>(`/workflow/requests/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ comments }),
  });

export const rejectRequest = (id: string, comments?: string) =>
  request<WorkflowRequest>(`/workflow/requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ comments }),
  });

export function timeAgo(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const s = Math.max(0, Math.round((now.getTime() - d.getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

