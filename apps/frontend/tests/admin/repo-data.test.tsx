import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import App from "../../src/admin/App";
import { ALL_MODULES, INTEGRATIONS, PLATFORM_SERVICES, SUITES } from "../../src/admin/data/architecture";
import { computeEntitlement } from "../../src/tenant/entitlements";
import { moduleAccess, type EntitlementView } from "../../src/admin/data/entitlement";
import { MOCK_USERS } from "../../src/admin/data/mockData";
import { LAYOUTS, MANIFESTS, MODULE_PERMISSIONS, PLANS, PROFILES, REFERENCE_PROFILE, ROLE_GRANTS, academyLabel } from "../../src/admin/data/repo";
import { ROLES, ROLE_LAYOUTS, findRole } from "../../src/admin/data/roles";
import { ENDPOINTS, allows } from "../../src/admin/data/apiAccess";

/** The admin's facts must come from the repository, not from the design's sample text. */
describe("admin catalogue matches the module manifests", () => {
  it("lists every module.yaml once, and nothing else", () => {
    expect(ALL_MODULES.map((m) => m.id).sort()).toEqual(Object.keys(MANIFESTS).sort());
  });

  it("uses each manifest's description and status", () => {
    for (const m of ALL_MODULES) {
      expect(m.description, m.id).toBe(MANIFESTS[m.id]!.description);
      expect(m.status, m.id).toBe(MANIFESTS[m.id]!.status);
    }
  });

  it("puts every feature module in the suite of its domain, including practice", () => {
    for (const s of SUITES) for (const m of s.modules) expect(MANIFESTS[m.id]!.domain, m.id).toBe(s.domain);
    expect(SUITES.map((s) => s.id)).toContain("practice");
    expect(PLATFORM_SERVICES.map((p) => p.id)).toEqual(expect.arrayContaining(["tenancy", "billing"]));
  });

  it("claims backend code only for identity, tenancy and billing", () => {
    expect(ALL_MODULES.filter((m) => m.implemented).map((m) => m.id).sort()).toEqual(["billing", "identity", "tenancy"]);
  });
});

describe("role & access reads the backend routers", () => {
  const find = (method: string, path: string) => ENDPOINTS.find((e) => e.method === method && e.path === path)!;
  const orgAdmin = { permissions: [...(ROLE_GRANTS["org-admin"] ?? [])], organisationId: "org-1" };
  const superAdmin = { permissions: findRole("super-admin")!.permissions, organisationId: null };

  it("parses each endpoint's requirement", () => {
    expect(find("POST", "/api/v1/identity/users").requires).toEqual({ kind: "permission", key: "tenancy:organisation:manage" });
    expect(find("GET", "/api/v1/identity/users").requires).toEqual({ kind: "organisation" });
    expect(find("POST", "/api/v1/identity/auth/login").requires).toEqual({ kind: "public" });
    expect(find("POST", "/api/v1/tenancy/admin/organisations/{org_id}/approve").requires).toEqual({ kind: "permission", key: "platform:organisations:manage" });
  });

  it("matches what the backend allows each admin", () => {
    expect(allows(find("POST", "/api/v1/identity/users"), orgAdmin)).toBe(true);
    expect(allows(find("GET", "/api/v1/tenancy/admin/organisations"), orgAdmin)).toBe(false);
    expect(allows(find("GET", "/api/v1/tenancy/admin/organisations"), superAdmin)).toBe(true);
    expect(allows(find("GET", "/api/v1/identity/users"), superAdmin)).toBe(false);
  });
});

describe("academy type label", () => {
  it("names sports-college as Sports College, from its profile title", () => {
    expect(PROFILES["sports-college"]!.title).toBe("Sports University / Sports College");
    expect(academyLabel(PROFILES["sports-college"]!)).toBe("Sports College");
  });

  it("is a part of each profile's title, or the whole title", () => {
    for (const p of Object.values(PROFILES)) {
      const label = academyLabel(p);
      expect(p.title.split(" / ").concat(p.title), p.profile).toContain(label);
    }
  });
});

describe("admin module access follows the entitlement rule", () => {
  const plan = PLANS.trial!;
  const view: EntitlementView = { source: "preview", profile: REFERENCE_PROFILE, planTitle: plan.title, entitlement: computeEntitlement(REFERENCE_PROFILE, plan) };

  it("includes feature modules only when the entitlement does", () => {
    for (const s of SUITES)
      for (const m of s.modules) {
        const path = `${s.domain}/${m.id}`;
        const expected = view.entitlement!.modules.has(path) ? "included" : REFERENCE_PROFILE.modules.includes(path) ? "upgrade" : "not-in-profile";
        expect(moduleAccess(m, view), path).toBe(expected);
      }
  });

  it("includes integrations from the profile that the plan allows (eos_core.entitlement)", () => {
    for (const m of INTEGRATIONS) {
      const inProfile = (REFERENCE_PROFILE.integrations ?? []).includes(m.id);
      const inPlan = plan.integrations.includes("*") || plan.integrations.includes(m.id);
      expect(moduleAccess(m, view), m.id).toBe(!inProfile ? "not-in-profile" : inPlan ? "included" : "upgrade");
    }
    expect(INTEGRATIONS.some((m) => moduleAccess(m, view) !== "not-in-profile")).toBe(true);
  });
});

describe("admin roles match the profile and platform roles", () => {
  it("are the reference profile's roles plus super-admin, with no invented role", () => {
    const ids = ROLES.map((r) => r.id);
    expect(ids).toEqual([...REFERENCE_PROFILE.roles.map((r) => r.id), "super-admin"]);
    expect(ids).toContain("org-admin");
    expect(ids).not.toContain("identity-admin");
    for (const r of REFERENCE_PROFILE.roles) expect(findRole(r.id)!.title).toBe(r.title);
  });

  it("hold only keys the repo defines, granted the way the backend grants them", () => {
    const defined = new Set(Object.values(MODULE_PERMISSIONS).flatMap((ps) => ps.map((p) => p.key)));
    for (const r of ROLES) for (const k of r.permissions) expect(defined.has(k), `${r.id}: ${k}`).toBe(true);
    expect(findRole("org-admin")!.permissions).toEqual([...(ROLE_GRANTS["org-admin"] ?? [])].sort());
    const superKeys = findRole("super-admin")!.permissions;
    expect(superKeys.length).toBeGreaterThan(0);
    for (const k of superKeys) expect(k.startsWith("platform:") || ROLE_GRANTS["super-admin"]?.has(k), k).toBe(true);
  });

  it("use the layout files as written", () => {
    for (const [id, layout] of Object.entries(ROLE_LAYOUTS)) expect(layout).toEqual(LAYOUTS[id]);
    expect(ROLE_LAYOUTS.coach!.extends).toBe("faculty");
    expect(ROLE_LAYOUTS.management!.widgets).toContain("productions.upcoming");
    expect(ROLE_LAYOUTS.management!.widgets).not.toContain("tournament-events.results");
  });

  it("assign sample users only to real roles", () => {
    for (const u of MOCK_USERS) expect(findRole(u.role), u.role).toBeDefined();
  });
});

describe("admin screens name no single institution", () => {
  beforeAll(() => {
    globalThis.ResizeObserver ??= class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    sessionStorage.setItem("eos.admin.preview", "1");
  });
  afterEach(cleanup);

  it.each(["/login", "/dashboard", "/admissions", "/users", "/roles", "/dashboards", "/modules", "/modules/hostel", "/audit-logs"])(
    "%s",
    async (path) => {
      if (path === "/login") sessionStorage.removeItem("eos.admin.preview");
      else sessionStorage.setItem("eos.admin.preview", "1");
      window.location.hash = path;
      const { container } = render(<App />);
      await waitFor(() => expect(container.textContent!.length).toBeGreaterThan(50));
      expect(container.textContent).not.toMatch(/MBSPSU|Punjab|Patiala|Maharaja|identity-admin|apps\/web|Cryptographically/);
    },
  );
});
