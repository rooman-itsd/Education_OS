/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/e-office) the dashboard widget
 * uses. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by
 * the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the
 * app shell stores after sign-in.
 */

export type FileStatus = "open" | "closed";

export type Priority = "normal" | "urgent" | "immediate";

/** A person. `name` is empty and `designation` null until identity names are available to modules. */
export interface UserRef {
  user_id: string;
  name: string;
  designation: string | null;
}

/** FileSummary: a file as lists show it. */
export interface FileSummary {
  id: string;
  organisation_id: string;
  /** <category code>/<year>/<sequence>, e.g. ADM/2026/0007. */
  number: string;
  subject: string;
  category_id: string;
  department_id: string | null;
  priority: Priority;
  confidential: boolean;
  status: FileStatus;
  holder: UserRef;
  /** ISO date-time the current holder received the file. */
  held_since: string;
  /** The action the sender asked for (e.g. "for approval"); null when none was given. */
  action_required: string | null;
  /** YYYY-MM-DD set when the file was sent; null means the default days for its priority apply. */
  due_on: string | null;
  /** Open, and today (Asia/Kolkata) is after the date the holding falls due. */
  overdue: boolean;
}

/**
 * GET /me/inbox: open files the caller holds, oldest received first, with counts over all of them (not
 * only the page).
 */
export interface Inbox {
  total: number;
  overdue: number;
  /** Files of priority urgent or immediate. */
  urgent: number;
  oldest_held_since: string | null;
  items: FileSummary[];
  /** Receipts sent to the caller and not yet attached to a file. */
  unattached_receipts: number;
  next_cursor: string | null;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/e-office";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class EOfficeApiError extends Error {
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

async function get<T>(path: string, query: Record<string, string | undefined> = {}, signal?: AbortSignal): Promise<T> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined) params.set(k, v);
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
    throw new EOfficeApiError(0, "The e-office service could not be reached.");
  }
  if (!res.ok) {
    // The contract's errors are { detail: { code, message } }; FastAPI's validation errors and the gateway's are { detail }.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string | { message?: string } } | undefined;
    throw new EOfficeApiError(res.status, body?.message ?? (typeof body?.detail === "string" ? body.detail : body?.detail?.message) ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** GET /me/inbox, first page of `limit` files (1 to 200). Permission e-office:file:use. */
export function getInbox(limit: number, signal?: AbortSignal): Promise<Inbox> {
  return get("/me/inbox", { limit: String(limit) }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof EOfficeApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "File data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load file data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof EOfficeApiError && (e.status === 401 || e.status === 403));
}
