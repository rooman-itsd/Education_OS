/**
 * Typed client for the parts of contracts/openapi.yaml the admissions frontend uses. The repo has no OpenAPI
 * generator yet; when packages/contracts ships one, this file is replaced by the generated client and the
 * types below must keep matching the contract's schemas.
 *
 * Paths are relative to the API base (VITE_API_URL, default /api/v1). Staff calls send the session token the app
 * shell stores after sign-in; the public tracking call sends none.
 */

export type ApplicationStatus =
  | "submitted"
  | "under_review"
  | "eligible"
  | "ineligible"
  | "offered"
  | "accepted"
  | "declined"
  | "rejected"
  | "withdrawn";

export type DocumentType = "identity_proof" | "academic_record" | "portfolio_evidence" | "other";
export type VerificationStatus = "pending" | "verified" | "rejected";
export type OfferStatus = "open" | "accepted" | "declined" | "expired" | "withdrawn";

/** contract ApplicantDetails */
export interface Applicant {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  date_of_birth?: string | null;
}

/** contract ApplicationDocument */
export interface ApplicationDocument {
  id: string;
  application_id: string;
  type: DocumentType;
  document_id: string;
  label?: string | null;
  verification_status: VerificationStatus;
  verification_note?: string | null;
  uploaded_at: string;
}

/** contract Offer, the fields the frontend reads */
export interface Offer {
  id: string;
  status: OfferStatus;
  note?: string | null;
  expires_at?: string | null;
  offered_at: string;
  decided_at?: string | null;
}

/** contract Application */
export interface Application {
  id: string;
  reference_number: string;
  applicant: Applicant;
  programme_id: string;
  academic_year: string;
  status: ApplicationStatus;
  documents: ApplicationDocument[];
  offer: Offer | null;
  submitted_at: string;
  decided_at?: string | null;
}

/** contract ApplicationPage */
export interface ApplicationPage {
  items: Application[];
  total: number;
  page: number;
  page_size: number;
}

/** contract DocumentQueueItem */
export interface DocumentQueueItem extends ApplicationDocument {
  reference_number: string;
  applicant_name: string;
}

/** contract DocumentQueuePage */
export interface DocumentQueuePage {
  items: DocumentQueueItem[];
  total: number;
  page: number;
  page_size: number;
}

/** contract MyApplications */
export interface MyApplications {
  items: Application[];
}

/** contract FunnelReport */
export interface FunnelReport {
  total: number;
  stages: { applied: number; eligible: number; offered: number; accepted: number };
  by_status: Partial<Record<ApplicationStatus, number>>;
}

const API_BASE = (import.meta as { env?: Record<string, string | undefined> }).env?.VITE_API_URL ?? "/api/v1";
const TOKEN_KEY = "eos.token";

export class AdmissionsApiError extends Error {
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

async function get<T>(path: string, { signal, auth = true }: { signal?: AbortSignal; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const t = auth ? token() : null;
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}/admissions${path}`, { headers, signal });
  if (!res.ok) throw new AdmissionsApiError(res.status, res.statusText || `HTTP ${res.status}`);
  return (await res.json()) as T;
}

async function post<T>(
  path: string,
  body: unknown,
  { signal, auth = true }: { signal?: AbortSignal; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const t = auth ? token() : null;
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API_BASE}/admissions${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let msg = res.statusText || `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err?.message) msg = err.message;
      else if (err?.detail?.message) msg = err.detail.message;
    } catch {
      // ignore JSON parse error
    }
    throw new AdmissionsApiError(res.status, msg);
  }
  return (await res.json()) as T;
}

/** GET /me/applications: caller's own applications. Permission admissions:self:read. */
export function listMyApplications(signal?: AbortSignal): Promise<MyApplications> {
  return get<MyApplications>("/me/applications", { signal });
}

/** POST /me/applications: link application to caller's account. Permission admissions:self:read. */
export function linkApplication(
  referenceNumber: string,
  email: string,
  signal?: AbortSignal,
): Promise<Application> {
  return post<Application>("/me/applications", { reference_number: referenceNumber.trim(), email: email.trim() }, { signal });
}

/** GET /applications: newest first. Permission admissions:application:read. */
export function listRecentApplications(pageSize: number, signal?: AbortSignal): Promise<ApplicationPage> {
  return get<ApplicationPage>(`/applications?page_size=${pageSize}`, { signal });
}

/** GET /documents: the verification queue, oldest upload first. Permission admissions:document:verify. */
export function listPendingDocuments(pageSize: number, signal?: AbortSignal): Promise<DocumentQueuePage> {
  return get<DocumentQueuePage>(`/documents?verification_status=pending&page_size=${pageSize}`, { signal });
}

/** GET /reports/funnel: counts only. Permission admissions:report:read. */
export function getFunnel(signal?: AbortSignal): Promise<FunnelReport> {
  return get<FunnelReport>("/reports/funnel", { signal });
}

/**
 * GET /public/{org_slug}/applications/track: public, no token. 404 when the organisation is unknown or the
 * reference number and email do not both match; the two are deliberately indistinguishable.
 */
export function trackApplication(
  orgSlug: string,
  referenceNumber: string,
  email: string,
  signal?: AbortSignal,
): Promise<Application> {
  const query = new URLSearchParams({ reference_number: referenceNumber.trim(), email: email.trim() });
  return get<Application>(`/public/${encodeURIComponent(orgSlug)}/applications/track?${query}`, { signal, auth: false });
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
  if (!(e instanceof AdmissionsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Admissions data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export function isAbort(e: unknown): boolean {
  return (e as { name?: string })?.name === "AbortError";
}
