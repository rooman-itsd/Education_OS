import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ExpiringContracts } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ContractsExpiringWidget, dueLabel } from "../src/widgets/ContractsExpiringWidget";

const V = "11111111-1111-4111-8111-111111111111";

const expiring = (over: Partial<ExpiringContracts> = {}): ExpiringContracts => ({
  within_days: 60,
  expiring_count: 2,
  expired_count: 1,
  items: [
    { contract_id: "c1", number: "AMC-000003", vendor_id: V, title: "UPS AMC", end_date: "2026-10-29", days_left: -3, renewal_draft_exists: false },
    { contract_id: "c2", number: "AMC-000001", vendor_id: V, title: "Generator AMC", end_date: "2026-11-16", days_left: 15, renewal_draft_exists: false },
    { contract_id: "c3", number: "AMC-000002", vendor_id: V, title: "Lift AMC", end_date: "2026-12-11", days_left: 40, renewal_draft_exists: true },
  ],
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

describe("amc-vendor-support.contracts-expiring widget", () => {
  it("is exported with the id and permission the Support Staff layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "amc-vendor-support.contracts-expiring");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("amc-vendor-support:contract:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(ContractsExpiringWidget);
  });

  it("lists contracts soonest first from GET /stats/contracts-expiring with the session token", async () => {
    const fetchMock = answer(200, expiring());
    vi.stubGlobal("fetch", fetchMock);
    render(<ContractsExpiringWidget role="support-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("UPS AMC")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.textContent?.match(/UPS|Generator|Lift/)?.[0])).toEqual(["UPS", "Generator", "Lift"]);
    expect(screen.getByText("Expired 3 days ago")).toBeTruthy();
    expect(screen.getByText("15 days left")).toBeTruthy();
    expect(screen.getByText("AMC-000002 · renewal drafted")).toBeTruthy();
    expect(screen.getByText("AMC-000001 · ends 2026-11-16")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Contracts expiring" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/amc-vendor-support/stats/contracts-expiring");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state with the window when nothing is due", async () => {
    vi.stubGlobal("fetch", answer(200, expiring({ expiring_count: 0, expired_count: 0, items: [] })));
    render(<ContractsExpiringWidget role="support-staff" />);
    expect(await screen.findByText("No contracts expiring")).toBeTruthy();
    expect(screen.getByText("Contracts ending in the next 60 days appear here.")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => expiring() });
    vi.stubGlobal("fetch", fetchMock);
    render(<ContractsExpiringWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load expiring contracts");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("UPS AMC")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet while the API is not mounted (404), and can retry", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<ContractsExpiringWidget role="support-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("AMC data is not available yet.");
    expect(alert.textContent).not.toContain("connection");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<ContractsExpiringWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("words how soon a contract ends", () => {
    expect(dueLabel(-1)).toEqual({ text: "Expired 1 day ago", tone: "danger" });
    expect(dueLabel(0)).toEqual({ text: "Ends today", tone: "danger" });
    expect(dueLabel(1)).toEqual({ text: "1 day left", tone: "warning" });
    expect(dueLabel(30)).toEqual({ text: "30 days left", tone: "warning" });
    expect(dueLabel(31)).toEqual({ text: "31 days left", tone: "info" });
  });
});
