/**
 * Typed client for selection-process API endpoints consumed by frontend widgets.
 */

export type ProcessStatus = "draft" | "open" | "closed";
export type CandidateStatus = "registered" | "in_progress" | "selected" | "waitlisted" | "rejected" | "withdrawn";
export type DecisionOutcome = "advance" | "hold" | "reject";

export interface Stage {
  id: string;
  process_id: string;
  name: string;
  sequence: number;
  description?: string | null;
}

export interface Panel {
  id: string;
  process_id: string;
  stage_id?: string | null;
  name: string;
  member_person_ids: string[];
}

export interface Process {
  id: string;
  organisation_id: string;
  type_id: string;
  title: string;
  academic_year?: string | null;
  status: ProcessStatus;
  stages: Stage[];
  panels: Panel[];
  candidate_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProcessPage {
  items: Process[];
  total: number;
  page: number;
  page_size: number;
}

export interface Decision {
  id: string;
  candidate_id: string;
  stage_id: string;
  panel_id?: string | null;
  decided_by: string;
  outcome: DecisionOutcome;
  score?: number | null;
  comments?: string | null;
  decided_at: string;
}

export interface Candidate {
  id: string;
  process_id: string;
  organisation_id: string;
  person_id: string;
  status: CandidateStatus;
  current_stage_id?: string | null;
  decisions: Decision[];
  registered_at: string;
  decided_at?: string | null;
}

export interface CandidatePage {
  items: Candidate[];
  total: number;
  page: number;
  page_size: number;
}

export interface Slot {
  id: string;
  process_id: string;
  stage_id?: string | null;
  candidate_id?: string | null;
  title: string;
  starts_at: string;
  ends_at: string;
  status: string;
  location?: string | null;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class SelectionProcessApiError extends Error {
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
  const res = await fetch(`${API_BASE}/selection-process${path}`, { headers, signal });
  if (!res.ok) throw new SelectionProcessApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function listOpenProcesses(pageSize = 6, signal?: AbortSignal): Promise<ProcessPage> {
  return get<ProcessPage>(`/processes?status=open&page_size=${pageSize}`, signal);
}

export async function listProcess(processId: string, signal?: AbortSignal): Promise<Process> {
  return get<Process>(`/processes/${processId}`, signal);
}

export async function listMyApplications(processId?: string, pageSize = 6, signal?: AbortSignal): Promise<CandidatePage> {
  const p = processId ? `/processes/${processId}/candidates?scope=mine&page_size=${pageSize}` : `/candidates?scope=mine&page_size=${pageSize}`;
  return get<CandidatePage>(p, signal);
}

export async function listToJudge(processId: string, pageSize = 6, signal?: AbortSignal): Promise<CandidatePage> {
  return get<CandidatePage>(`/processes/${processId}/candidates?scope=managed&status=registered,in_progress&page_size=${pageSize}`, signal);
}

export async function listUpcomingSlots(limit = 6, signal?: AbortSignal): Promise<Slot[]> {
  return get<Slot[]>(`/slots/upcoming?limit=${limit}`, signal);
}

