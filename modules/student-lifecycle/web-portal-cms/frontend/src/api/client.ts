/**
 * Typed client for the CMS parts of contracts/openapi.yaml the dashboard widgets use (the public sign-up pages use
 * public-client.ts). The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced
 * by the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). Calls send the session token the app shell
 * stores after sign-in: reading the CMS needs a signed-in member of the organisation (docs/prd.md §11 D1).
 */

/** contract Announcement, the fields the widget reads. `body` is plain text, never HTML. */
export interface Announcement {
  id: string;
  title: string;
  body: string;
  starts_at: string | null;
  ends_at: string | null;
  published_at: string | null;
}

/** contract AnnouncementPage */
export interface AnnouncementPage {
  items: Announcement[];
  total: number;
  page: number;
  page_size: number;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class CmsApiError extends Error {
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
  const res = await fetch(`${API_BASE}/web-portal-cms${path}`, { headers, signal });
  if (!res.ok) throw new CmsApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

/** GET /announcements: the organisation's visible announcements, most recently published first. */
export function listAnnouncements(pageSize: number, signal?: AbortSignal): Promise<AnnouncementPage> {
  return get<AnnouncementPage>(`/announcements?page_size=${pageSize}`, signal);
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
  if (!(e instanceof CmsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Announcements are not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export function isAbort(e: unknown): boolean {
  return (e as { name?: string })?.name === "AbortError";
}
