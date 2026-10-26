import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { byRole, type User } from "../src/api/client";
import { widgets } from "../src/widgets";
import { UsersAndRoles } from "../src/widgets/UsersAndRoles";

const user = (id: string, roles: string[], status = "active"): User => ({ id, organisation_id: "o1", email: `${id}@x.example.com`, name: id, roles, is_super_admin: false, status, created_at: "2026-10-01T00:00:00+00:00" });
const users = [user("a", ["org-admin"]), user("b", ["student"]), user("c", ["student"]), user("d", ["faculty", "department-admin"], "disabled")];

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("identity.users-and-roles", () => {
  it("is exported with the id and permission the Organisation Admin layout expects", () => {
    const w = widgets.find((x) => x.id === "identity.users-and-roles");
    expect(w?.permission).toBe("identity:user:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(UsersAndRoles);
  });

  it("counts users, active and disabled, and lists roles largest first", async () => {
    const fetchMock = answer(200, users);
    vi.stubGlobal("fetch", fetchMock);
    render(<UsersAndRoles role="org-admin" />);
    expect(await screen.findByText("4 users")).toBeTruthy();
    expect(screen.getByText("3 active")).toBeTruthy();
    expect(screen.getByText("1 disabled")).toBeTruthy();
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(rows[1]).toContain("Student");
    expect(rows[1]).toContain("2");
    expect(rows.slice(2).join(" ")).toContain("Org admin");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/identity/users");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("follows the error convention: not available on 404, no retry on 403", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<UsersAndRoles role="org-admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("User data is not available yet.");
    cleanup();
    vi.stubGlobal("fetch", answer(403, {}));
    render(<UsersAndRoles role="org-admin" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("byRole counts a user once per role held", () => {
    expect(byRole(users)).toEqual([
      { role: "student", count: 2 },
      { role: "department-admin", count: 1 },
      { role: "faculty", count: 1 },
      { role: "org-admin", count: 1 },
    ]);
  });
});
