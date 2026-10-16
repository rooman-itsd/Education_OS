import { expect, type APIRequestContext } from "@playwright/test";
import { SUPER_ADMIN } from "../stack";

/**
 * Setup for dashboard journeys: an active organisation and one user with the role under test, created
 * through the API. The onboarding journey covers registration and approval through the UI; dashboard
 * journeys start from a signed-out user who already exists.
 */

export interface DashboardUser {
  organisation: { id: string; name: string; slug: string };
  email: string;
  password: string;
  /** The user's API token, for checks the journey makes outside the browser. */
  token: string;
}

async function ok<T>(response: Awaited<ReturnType<APIRequestContext["post"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

async function login(request: APIRequestContext, email: string, password: string): Promise<string> {
  return (await ok<{ token: string }>(await request.post("/api/v1/identity/auth/login", { data: { email, password } })))
    .token;
}

/** Register, verify (dev mode returns the token), approve as the super admin, then add a user with `role`. */
export async function organisationWithUser(
  request: APIRequestContext,
  { academyType, role }: { academyType: string; role: string },
): Promise<DashboardUser> {
  const run = Date.now().toString(36);
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
  await ok(await request.post("/api/v1/identity/users", { headers: orgAdmin, data: { ...user, roles: [role] } }));

  return {
    organisation: { id: org.id, name: org.name, slug: org.slug },
    email: user.email,
    password: user.password,
    token: await login(request, user.email, user.password),
  };
}
