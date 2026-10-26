import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { bySuite, humanise, type Entitlement } from "../src/api/client";
import { widgets } from "../src/widgets";
import { EnabledModules } from "../src/widgets/EnabledModules";

const entitlement: Entitlement = {
  organisation_id: "o1",
  plan: "trial",
  academy_type: "music-academy",
  modules: ["academics/lms", "academics/academic-management", "campus-life/hostel"],
  module_names: ["lms", "academic-management", "hostel"],
  integrations: [],
  limits: { users: 25, students: 500, storage_gb: 2 },
  upgradable_modules: ["finance-operations/fees-accounts", "facilities/facility-booking"],
  status: "active",
  subscription_status: "trialing",
};

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("tenancy.enabled-modules", () => {
  it("is exported with the id and permission the Organisation Admin layout expects", () => {
    const w = widgets.find((x) => x.id === "tenancy.enabled-modules");
    expect(w?.permission).toBe("tenancy:organisation:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(EnabledModules);
  });

  it("groups the modules by suite and counts what a higher plan would unlock", async () => {
    const fetchMock = answer(200, entitlement);
    vi.stubGlobal("fetch", fetchMock);
    render(<EnabledModules role="org-admin" />);
    expect(await screen.findByText("Academics")).toBeTruthy();
    expect(screen.getByText("Lms, Academic management")).toBeTruthy();
    expect(screen.getByText("2 on")).toBeTruthy();
    expect(screen.getByText("Campus life")).toBeTruthy();
    expect(screen.getByText("2 more on a higher plan")).toBeTruthy();
    expect(screen.getByText("Fees accounts, Facility booking")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/tenancy/organisation/entitlement");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is on, and the convention's error states", async () => {
    vi.stubGlobal("fetch", answer(200, { ...entitlement, modules: [], upgradable_modules: [] }));
    render(<EnabledModules role="org-admin" />);
    expect(await screen.findByText("No modules are on")).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", answer(503, {}));
    render(<EnabledModules role="org-admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Organisation data is not available yet.");
    cleanup();
    vi.stubGlobal("fetch", answer(401, {}));
    render(<EnabledModules role="org-admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("helpers: bySuite keeps path order, humanise words an id", () => {
    expect(bySuite(["a/x", "b/y", "a/z"])).toEqual([{ suite: "a", modules: ["x", "z"] }, { suite: "b", modules: ["y"] }]);
    expect(humanise("finance-operations")).toBe("Finance operations");
    expect(humanise("user.created")).toBe("User created");
  });
});
