/**
 * Typed client for the parts of contracts/openapi.yaml (servers: /api/v1/training-video-analysis) the dashboard
 * widgets use. The repo has no OpenAPI generator yet; when packages/contracts ships one, this file is replaced by
 * the generated client and the types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). The session token is the one the app shell
 * stores after sign-in.
 */

/** A page of a list endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
}

/** contract TrainingVideo (the fields the widgets read). */
export interface TrainingVideo {
  id: string;
  session_id?: string | null;
  uploader_id: string;
  title: string;
  description?: string;
  video_url: string;
  thumbnail_url?: string | null;
  duration_seconds: number;
  /** date-time */
  recorded_at: string;
  /** date-time */
  created_at: string;
}

const API_BASE =
  ((import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1") + "/training-video-analysis";

/** The session token the shell stores after sign-in (apps/frontend, src/api/client.ts). */
const TOKEN_KEY = "eos.token";

/** A failed call. `status` is the HTTP status, or 0 when the service could not be reached. */
export class TrainingVideoApiError extends Error {
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
    throw new TrainingVideoApiError(0, "The training video service could not be reached.");
  }
  if (!res.ok) {
    // ErrorResponse { code, message } from the contract; { detail } from the gateway.
    const body = (await res.json().catch(() => undefined)) as { message?: string; detail?: string } | undefined;
    throw new TrainingVideoApiError(res.status, body?.message ?? body?.detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

/**
 * GET /videos, most recently recorded first. `annotated: false` gives only the videos nobody has annotated yet,
 * `true` only annotated ones; `total` counts every match. Staff see the organisation's videos; an athlete sees only
 * the videos of their sessions and the ones annotated about them. Permission training-video-analysis:video:read.
 */
export function listVideos(query: { annotated?: boolean; limit: number }, signal?: AbortSignal): Promise<Page<TrainingVideo>> {
  return get("/videos", { annotated: query.annotated === undefined ? undefined : String(query.annotated), limit: query.limit }, signal);
}

/** Words for a failed call, for the widget's error state. */
export function errorMessage(e: unknown): string {
  if (e instanceof TrainingVideoApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503) return "Training video data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
  }
  // Server wording (a 500's message, a gateway page) is never the headline.
  return "Could not load training video data.";
}

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof TrainingVideoApiError && (e.status === 401 || e.status === 403));
}
