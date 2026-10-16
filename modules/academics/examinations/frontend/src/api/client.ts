import type { ExamSessionPage, HallTicketReport, ResultsPendingReport } from "./types";

// The examinations API (contracts/openapi.yaml, servers: /api/v1/examinations). A stand-in for the
// generated client: same paths and shapes, no logic of its own.

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/examinations";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

export class ExaminationsApiError extends Error {
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
    throw new ExaminationsApiError(0, "The examinations service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from this contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string } | undefined;
    throw new ExaminationsApiError(res.status, body?.message ?? body?.detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** Local calendar date as YYYY-MM-DD (the contract's date_from is a date, not a timestamp). */
export function today(now = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** GET /sessions?date_from=today&status=scheduled: upcoming sessions ordered by start time. */
export function listUpcomingSessions(limit: number, signal?: AbortSignal): Promise<ExamSessionPage> {
  return get("/sessions", { date_from: today(), status: "scheduled", limit }, signal);
}

/** GET /reports/hall-tickets: per exam cycle, defaulting to cycles scheduled or in progress. */
export function getHallTicketReport(signal?: AbortSignal): Promise<HallTicketReport> {
  return get("/reports/hall-tickets", {}, signal);
}

/** GET /reports/results-pending: per exam cycle, defaulting to cycles in evaluation. */
export function getResultsPendingReport(signal?: AbortSignal): Promise<ResultsPendingReport> {
  return get("/reports/results-pending", {}, signal);
}
