import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { timeAgo, type AuditRecord } from "../src/api/client";
import { widgets } from "../src/widgets";
import { RecentActivity, SHOWN } from "../src/widgets/RecentActivity";
import { SuperAdminActions } from "../src/widgets/SuperAdminActions";

const rec = (over: Partial<AuditRecord> = {}): AuditRecord => ({
  id: "r1",
  organisation_id: "o1",
  module: "identity",
  action: "user.created",
  entity_type: "user",
  entity_id: "u9",
  actor: "u1",
  actor_name: "Asha Rao",
  occurred_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  ...over,
});

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("audit.recent-activity", () => {
  it("is exported with the id and permission the Organisation Admin layout expects", () => {
    const w = widgets.find((x) => x.id === "audit.recent-activity");
    expect(w?.permission).toBe("audit:record:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(RecentActivity);
  });

  it("lists the latest records with who and when, asking for the newest few", async () => {
    const fetchMock = answer(200, { items: [rec(), rec({ id: "r2", module: "hostel", action: "allocation.confirmed", summary: "Bed 2 confirmed for Priya", actor: null, actor_name: undefined })], total: 12 });
    vi.stubGlobal("fetch", fetchMock);
    render(<RecentActivity role="org-admin" />);
    expect(await screen.findByText("User created")).toBeTruthy();
    expect(screen.getByText("Identity · Asha Rao · 5 min ago")).toBeTruthy();
    expect(screen.getByText("Bed 2 confirmed for Priya")).toBeTruthy();
    expect(screen.getByText(/Hostel · System/)).toBeTruthy();
    expect(screen.getByText(`${12 - SHOWN} more`)).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/audit/records?limit=${SHOWN}`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says the data is not available while platform/audit is not mounted, and empty when nothing is recorded", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<RecentActivity role="org-admin" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Audit data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", answer(200, { items: [], total: 0 }));
    render(<RecentActivity role="org-admin" />);
    expect(await screen.findByText("Nothing recorded yet")).toBeTruthy();
  });

  it("timeAgo words a timestamp and survives an invalid one", () => {
    const now = new Date("2026-10-23T12:00:00Z");
    expect(timeAgo("2026-10-23T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-10-23T11:30:00Z", now)).toBe("30 min ago");
    expect(timeAgo("2026-10-23T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2026-10-21T12:00:00Z", now)).toBe("2 d ago");
    expect(timeAgo("2026-09-01T12:00:00Z", now)).toBe("1 Sept");
    expect(timeAgo("not-a-date", now)).toBe("");
  });
});

describe("audit.super-admin-actions", () => {
  it("is exported with the id and permission the Super Admin layout expects", () => {
    const w = widgets.find((x) => x.id === "audit.super-admin-actions");
    expect(w?.permission).toBe("platform:audit:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(SuperAdminActions);
  });

  it("lists platform-level actions for the super admin", async () => {
    const fetchMock = answer(200, {
      items: [
        rec({
          id: "p1",
          organisation_id: null,
          module: "tenancy",
          action: "organisation.approved",
          summary: "Approved Delhi Academy",
          actor: "root",
          actor_name: "Super Admin",
        }),
      ],
      total: 1,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<SuperAdminActions role="super-admin" />);
    expect(await screen.findByText("Approved Delhi Academy")).toBeTruthy();
    expect(screen.getByText("Tenancy · Super Admin · 5 min ago")).toBeTruthy();
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/audit/records?limit=${SHOWN}`);
  });
});
