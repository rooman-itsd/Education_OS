import { expect, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { SUPER_ADMIN } from "../stack";

/**
 * Setup for dashboard journeys: an active organisation and one user with the role under test, created
 * through the API. The onboarding journey covers registration and approval through the UI; dashboard
 * journeys start from a signed-out user who already exists.
 */

export interface DashboardUser {
  organisation: { id: string; name: string; slug: string };
  /** The user's identity id, for records that refer to a user (a grant's investigators, for example). */
  id: string;
  email: string;
  password: string;
  /** The user's API token, for checks the journey makes outside the browser. */
  token: string;
}

/**
 * A run id for emails and slugs: the time plus a random suffix, so workers registering in the same millisecond do
 * not collide (409). `e2e-` + 8 time chars + `-` + 6 hex stays well within the slug rules (lowercase, digits, hyphens, 40).
 */
function runId(): string {
  return `${Date.now().toString(36)}-${randomUUID().replace(/-/g, "").slice(0, 6)}`;
}

async function ok<T>(response: Awaited<ReturnType<APIRequestContext["post"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

/**
 * Sign in through the API. Journeys running in parallel all sign in from one address, so a 429 from the sign-in
 * rate limit waits the `retry_after` it names (a few seconds at most) and tries again.
 */
export async function login(request: APIRequestContext, email: string, password: string): Promise<string> {
  for (let attempt = 0; ; attempt++) {
    const response = await request.post("/api/v1/identity/auth/login", { data: { email, password } });
    if (response.status() !== 429 || attempt >= 5) return (await ok<{ token: string }>(response)).token;
    const { retry_after } = (await response.json()) as { retry_after?: number };
    await new Promise((resolve) => setTimeout(resolve, Math.min(Math.max(retry_after ?? 1, 1), 10) * 1000));
  }
}

/**
 * Register, verify (dev mode returns the token), approve as the super admin, then add a user with `role`.
 * `extraRoles` come after it: the dashboard follows the first role, and the token also carries the extra roles'
 * permissions, so a journey can create its data through the API as the same user.
 */
export async function organisationWithUser(
  request: APIRequestContext,
  { academyType, role, extraRoles = [] }: { academyType: string; role: string; extraRoles?: string[] },
): Promise<DashboardUser> {
  const run = runId();
  const admin = { name: "E2E Admin", email: `admin@e2e-${run}.example.com`, password: "Passw0rd!e2e" };

  const org = await ok<{ id: string; name: string; slug: string; verification_token: string }>(
    await request.post("/api/v1/tenancy/register", {
      data: {
        organisation_name: `E2E ${role} ${run}`,
        slug: `e2e-${run}`,
        academy_type: academyType,
        admin,
        accepted_terms: true,
      },
    }),
  );
  await ok(await request.post("/api/v1/tenancy/register/verify", { data: { token: org.verification_token } }));

  const root = { Authorization: `Bearer ${await login(request, SUPER_ADMIN.email, SUPER_ADMIN.password)}` };
  await ok(await request.post(`/api/v1/tenancy/admin/organisations/${org.id}/approve`, { headers: root, data: { reason: "e2e" } }));

  const user = { name: "E2E User", email: `${role}@e2e-${run}.example.com`, password: "Passw0rd!e2e" };
  const orgAdmin = { Authorization: `Bearer ${await login(request, admin.email, admin.password)}` };
  const created = await ok<{ id: string }>(
    await request.post("/api/v1/identity/users", { headers: orgAdmin, data: { ...user, roles: [role, ...extraRoles] } }),
  );

  return {
    organisation: { id: org.id, name: org.name, slug: org.slug },
    id: created.id,
    email: user.email,
    password: user.password,
    token: await login(request, user.email, user.password),
  };
}

/** Register, verify and approve an organisation and return its admin (the `org-admin` role) signed in. */
export async function organisationAdmin(request: APIRequestContext, { academyType }: { academyType: string }): Promise<DashboardUser> {
  const run = runId();
  const admin = { name: "E2E Admin", email: `admin@e2e-${run}.example.com`, password: "Passw0rd!e2e" };
  const org = await ok<{ id: string; name: string; slug: string; verification_token: string }>(
    await request.post("/api/v1/tenancy/register", {
      data: { organisation_name: `E2E org-admin ${run}`, slug: `e2e-${run}`, academy_type: academyType, admin, accepted_terms: true },
    }),
  );
  await ok(await request.post("/api/v1/tenancy/register/verify", { data: { token: org.verification_token } }));
  const root = { Authorization: `Bearer ${await login(request, SUPER_ADMIN.email, SUPER_ADMIN.password)}` };
  await ok(await request.post(`/api/v1/tenancy/admin/organisations/${org.id}/approve`, { headers: root, data: { reason: "e2e" } }));
  const token = await login(request, admin.email, admin.password);
  const me = await ok<{ id: string }>(await request.get("/api/v1/identity/auth/me", { headers: { Authorization: `Bearer ${token}` } }));
  return {
    organisation: { id: org.id, name: org.name, slug: org.slug },
    id: me.id,
    email: admin.email,
    password: admin.password,
    token,
  };
}

/** Add a user with `role` to the admin's organisation and return them signed in. */
export async function addUser(request: APIRequestContext, admin: DashboardUser, role: string): Promise<DashboardUser> {
  const user = { name: `E2E ${role}`, email: `${role}@${admin.organisation.slug}.example.com`, password: "Passw0rd!e2e" };
  const created = await ok<{ id: string }>(
    await request.post("/api/v1/identity/users", { headers: { Authorization: `Bearer ${admin.token}` }, data: { ...user, roles: [role] } }),
  );
  return {
    organisation: admin.organisation,
    id: created.id,
    email: user.email,
    password: user.password,
    token: await login(request, user.email, user.password),
  };
}
