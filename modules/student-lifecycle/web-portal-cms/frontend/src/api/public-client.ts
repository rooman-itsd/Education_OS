/**
 * Typed client for the PUBLIC platform endpoints the sign-up page composes.
 *
 * web-portal-cms owns no registration/plan logic (docs/prd.md §3); the public site calls these
 * already-public endpoints directly, exactly as docs/integration-points.md describes:
 *   - platform/billing   GET  /billing/plans            (public)
 *   - platform/tenancy   GET  /tenancy/academy-types    (public)
 *   - platform/tenancy   POST /tenancy/register         (public)
 *   - platform/tenancy   POST /tenancy/register/verify  (public)
 *
 * No auth token is attached — every endpoint here is public. No other module's internals are touched.
 */

/** Base path for the platform API. In the app, nginx/Vite proxies /api/ to the API container. */
const API_BASE =
  (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? "/api/v1";

export class PublicApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "PublicApiError";
  }
}

async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  let body = init.body;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers, body });
  if (res.status === 204) return undefined as T;
  const data = (await res.json().catch(() => undefined)) as unknown;
  if (!res.ok) {
    const detail = (data as { detail?: string } | undefined)?.detail ?? res.statusText;
    throw new PublicApiError(res.status, detail);
  }
  return data as T;
}

// ---- Shapes (mirror the platform contracts; see platform/billing and platform/tenancy) ----

/** platform/tenancy GET /academy-types — one academy type (institution profile). */
export interface AcademyType {
  id: string;
  title: string;
  description: string;
  specialized_suites?: string[];
}

/** platform/billing GET /plans — one plan (Plan.to_dict). Prices are seed/default data the super admin can edit. */
export interface Plan {
  id: string;
  title: string;
  description: string;
  price_per_month: number;
  currency: string;
  trial_days: number | null;
  suites: string[];
  modules: string[];
  specialized_suites: number | "all";
  integrations: string[];
  limits: { users?: number; students?: number; storage_gb?: number };
  after_trial: string;
  published: boolean;
}

/** Body for platform/tenancy POST /register. Note: there is no `plan` field — registration starts the trial. */
export interface RegistrationInput {
  organisation_name: string;
  slug: string;
  academy_type: string;
  country?: string;
  admin: { name: string; email: string; password: string };
  accepted_terms: boolean;
}

/** platform/tenancy POST /register response. `verification_token` is present only in dev mode (EOS_DEV_MODE=true). */
export interface RegisteredOrganisation {
  id: string;
  slug: string;
  name: string;
  academy_type: string;
  status: string;
  verification_token?: string;
}

/** platform/tenancy POST /register/verify response. status is `pending_approval` until a super admin approves. */
export interface VerifiedOrganisation {
  id: string;
  slug: string;
  status: string;
}

// ---- Calls ----

export const getAcademyTypes = (): Promise<AcademyType[]> => request<AcademyType[]>("/tenancy/academy-types");

/** Only published plans are returned by the public endpoint. */
export const getPlans = (): Promise<Plan[]> => request<Plan[]>("/billing/plans");

export const register = (body: RegistrationInput): Promise<RegisteredOrganisation> =>
  request<RegisteredOrganisation>("/tenancy/register", { method: "POST", json: body });

export const verifyRegistration = (token: string): Promise<VerifiedOrganisation> =>
  request<VerifiedOrganisation>("/tenancy/register/verify", { method: "POST", json: { token } });
