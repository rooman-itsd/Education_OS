import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DueAsset, VerificationDue } from "../src/api/client";
import { widgets } from "../src/widgets";
import { AuditDueWidget } from "../src/widgets/AuditDueWidget";

const asset = (over: Partial<DueAsset>): DueAsset => ({
  asset_id: "a-1",
  tag: "AST-IT-00001",
  name: "Projector",
  location: "Hall",
  next_verification_due: "2026-09-01",
  overdue: true,
  ...over,
});

const due = (over: Partial<VerificationDue> = {}): VerificationDue => ({
  within_days: 30,
  overdue_count: 1,
  due_soon_count: 1,
  assets: [asset({}), asset({ asset_id: "a-2", tag: "AST-IT-00002", name: "Printer", location: null, next_verification_due: "2026-11-01", overdue: false })],
  open_cycles: [{ id: "c-1", name: "Q4 audit", due_on: "2026-10-31", status: "in_progress", counts: { total: 40, pending: 15 } }],
  ...over,
});

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("asset-management.audit-due widget", () => {
  it("is exported with the id and permission the Facility Staff layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "asset-management.audit-due");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("asset-management:asset:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(AuditDueWidget);
  });

  it("shows open cycles with progress, then due assets overdue first, from GET /verifications/due", async () => {
    const fetchMock = answer(200, due());
    vi.stubGlobal("fetch", fetchMock);
    render(<AuditDueWidget role="facility-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Q4 audit")).toBeTruthy();
    expect(screen.getByText("25 of 40 checked · due 31 Oct")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[1]?.textContent).toContain("AST-IT-00001 · Projector");
    expect(rows[1]?.textContent).toContain("Overdue");
    expect(rows[2]?.textContent).toContain("Due soon");
    expect(screen.getByText("No location · due 1 Nov")).toBeTruthy();
    expect(screen.getByLabelText("Verification counts").textContent).toBe("1 overdue · 1 due in 30 days");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/asset-management/verifications/due");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows five assets and how many more there are", async () => {
    const many = Array.from({ length: 8 }, (_, i) => asset({ asset_id: `a-${i}`, tag: `AST-${i}` }));
    vi.stubGlobal("fetch", answer(200, due({ assets: many, open_cycles: [], overdue_count: 8, due_soon_count: 0 })));
    render(<AuditDueWidget role="facility-staff" />);
    expect(await screen.findByText("3 more")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
  });

  it("shows an empty state when nothing is due and no cycle is open, and copes without open_cycles", async () => {
    vi.stubGlobal("fetch", answer(200, { within_days: 30, overdue_count: 0, due_soon_count: 0, assets: [] }));
    render(<AuditDueWidget role="facility-staff" />);
    expect(await screen.findByText("Nothing due for verification")).toBeTruthy();
    expect(screen.getByText("Assets due within 30 days appear here.")).toBeTruthy();
  });

  it("says the service is not available yet when it is missing or down, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => due() });
    vi.stubGlobal("fetch", fetchMock);
    render(<AuditDueWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Asset data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Q4 audit")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the session has expired (401) or access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, {}));
    render(<AuditDueWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(401, {}));
    render(<AuditDueWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("names any other failure without blaming the connection, and still retries", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<AuditDueWidget role="facility-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load assets due for verification");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
