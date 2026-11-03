import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { approvalQueue, countByStatus, initials, newest, timeAgo, type Organisation } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ApprovalQueue } from "../src/widgets/ApprovalQueue";
import { OrganisationsByStatus } from "../src/widgets/OrganisationsByStatus";
import { RecentRegistrations } from "../src/widgets/RecentRegistrations";

function org(name: string, over: Partial<Organisation> = {}): Organisation {
  return {
    id: name.toLowerCase().replace(/\s+/g, "-"),
    name,
    slug: name.toLowerCase().replace(/\s+/g, "-"),
    academy_type: "music-academy",
    requested_academy_type: null,
    country: "IN",
    status: "active",
    status_reason: null,
    plan: "trial",
    trial_ends_at: null,
    created_at: "2026-10-01T10:00:00Z",
    ...over,
  };
}

// As GET /admin/organisations answers: newest first.
const ORGS: Organisation[] = [
  org("Fresh Arts", { status: "pending_verification", created_at: "2026-10-30T09:00:00Z" }),
  org("Late Dance", { status: "pending_approval", academy_type: "dance-academy", created_at: "2026-10-29T09:00:00Z" }),
  org("Moving Music", { requested_academy_type: "performing-arts-academy", created_at: "2026-10-20T09:00:00Z" }),
  org("Early Law", { status: "pending_approval", academy_type: "law-school", created_at: "2026-10-10T09:00:00Z" }),
  org("Quiet Sports", { status: "suspended", academy_type: "sports-college", plan: "standard", created_at: "2026-09-01T09:00:00Z" }),
  org("Gone Design", { status: "archived", requested_academy_type: "design-school", created_at: "2026-08-01T09:00:00Z" }),
  org("Old Drama", { created_at: "2026-07-01T09:00:00Z" }),
];

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("super admin widgets: registration", () => {
  it.each(["tenancy.approval-queue", "tenancy.organisations-by-status", "tenancy.recent-registrations"])(
    "%s is exported with the super admin's permission, as super-admin.yaml expects",
    (id) => {
      const w = widgets.find((x) => x.id === id);
      expect(w?.permission).toBe("platform:organisations:read");
      expect(w?.kind).toBe("list");
    },
  );
});

describe("helpers", () => {
  it("queues registrations and package changes oldest first, never archived ones or plain active ones", () => {
    const q = approvalQueue(ORGS);
    expect(q.map((a) => [a.organisation.name, a.kind, a.package])).toEqual([
      ["Early Law", "registration", "law-school"],
      ["Moving Music", "package-change", "performing-arts-academy"],
      ["Late Dance", "registration", "dance-academy"],
    ]);
  });

  it("counts every status, zero included, in the contract's order", () => {
    expect(countByStatus(ORGS)).toEqual([
      { status: "pending_verification", count: 1 },
      { status: "pending_approval", count: 2 },
      { status: "active", count: 2 },
      { status: "suspended", count: 1 },
      { status: "archived", count: 1 },
    ]);
    // A status nobody is in still shows, with 0: never mistaken for "not counted".
    expect(countByStatus([org("Only One")])).toEqual([
      { status: "pending_verification", count: 0 },
      { status: "pending_approval", count: 0 },
      { status: "active", count: 1 },
      { status: "suspended", count: 0 },
      { status: "archived", count: 0 },
    ]);
  });

  it("takes the newest n whatever the order it gets", () => {
    expect(newest([...ORGS].reverse(), 3).map((o) => o.name)).toEqual(["Fresh Arts", "Late Dance", "Moving Music"]);
  });

  it("formats times and initials", () => {
    const now = new Date("2026-10-31T10:00:00Z");
    expect(timeAgo("2026-10-31T09:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-10-31T07:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-10-29T10:00:00Z", now)).toBe("2 d ago");
    expect(timeAgo(null, now)).toBe("");
    expect(timeAgo("not a date", now)).toBe("");
    expect(initials("Rooman Music Academy")).toBe("RM");
    expect(initials("Solo")).toBe("SO");
  });
});

describe("tenancy.approval-queue", () => {
  it("lists what waits, oldest first, with the count, from the admin list with the session token", async () => {
    const fetchMock = answer(200, ORGS);
    vi.stubGlobal("fetch", fetchMock);
    render(<ApprovalQueue role="super-admin" />);
    expect(await screen.findByText("3 waiting")).toBeTruthy();
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(rows[0]).toContain("Early Law");
    expect(rows[0]).toContain("New registration · Law school");
    expect(rows[1]).toContain("Package change · Music academy → Performing arts academy");
    expect(rows[2]).toContain("Late Dance");
    expect(screen.queryByText("Gone Design")).toBeNull();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/tenancy/admin/organisations");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says when nothing waits", async () => {
    vi.stubGlobal("fetch", answer(200, [org("Calm", {})]));
    render(<ApprovalQueue role="super-admin" />);
    expect(await screen.findByText("Nothing waiting for approval")).toBeTruthy();
  });
});

describe("tenancy.organisations-by-status", () => {
  it("shows the total and a count for every status", async () => {
    vi.stubGlobal("fetch", answer(200, ORGS));
    render(<OrganisationsByStatus role="super-admin" />);
    expect(await screen.findByText("7 organisations in all")).toBeTruthy();
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(rows).toEqual(["Pending verification1", "Pending approval2", "Active2", "Suspended1", "Archived1"]);
  });

  it("says when there are none", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<OrganisationsByStatus role="super-admin" />);
    expect(await screen.findByText("No organisations yet")).toBeTruthy();
  });
});

describe("tenancy.recent-registrations", () => {
  it("shows the five newest with package, plan and status", async () => {
    vi.stubGlobal("fetch", answer(200, ORGS));
    render(<RecentRegistrations role="super-admin" />);
    expect(await screen.findByText("Fresh Arts")).toBeTruthy();
    const rows = screen.getAllByRole("listitem").map((li) => li.textContent ?? "");
    expect(rows).toHaveLength(5);
    expect(rows[0]).toContain("Pending verification");
    expect(rows[4]).toContain("Quiet Sports");
    expect(rows[4]).toContain("Sports college · Standard plan");
    expect(rows[4]).toContain("Suspended");
    expect(screen.queryByText("Old Drama")).toBeNull();
  });

  it("says when there are none", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<RecentRegistrations role="super-admin" />);
    expect(await screen.findByText("No registrations yet")).toBeTruthy();
  });
});

describe("error states, as the other widgets", () => {
  it.each([
    [403, "You do not have access to this."],
    [503, "Organisation data is not available yet."],
  ])("answers %i with %s in every super admin widget", async (status, text) => {
    for (const W of [ApprovalQueue, OrganisationsByStatus, RecentRegistrations]) {
      vi.stubGlobal("fetch", answer(status, {}));
      render(<W role="super-admin" />);
      expect(await screen.findByText(text)).toBeTruthy();
      cleanup();
    }
  });
});
