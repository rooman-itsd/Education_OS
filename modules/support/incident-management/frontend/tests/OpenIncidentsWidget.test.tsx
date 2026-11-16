import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpenCounts } from "../src/api/client";
import { widgets } from "../src/widgets";
import { describeFailure, OpenIncidentsWidget, statusLine } from "../src/widgets/OpenIncidentsWidget";
import { IncidentManagementApiError } from "../src/api/client";

const counts = (over: Partial<OpenCounts> = {}): OpenCounts => ({
  total_open: 3,
  by_severity: [
    { severity: "critical", count: 2 },
    { severity: "high", count: 0 },
    { severity: "medium", count: 0 },
    { severity: "low", count: 1 },
  ],
  by_status: [
    { status: "open", count: 1 },
    { status: "investigating", count: 1 },
    { status: "mitigated", count: 1 },
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

describe("incident-management.open widget", () => {
  it("is exported with the id and permission the Support Staff layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "incident-management.open");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("incident-management:incident:read");
    expect(w?.kind).toBe("list");
    expect(w?.size).toBe("1x1");
    expect(w?.component).toBe(OpenIncidentsWidget);
  });

  it("shows one row per severity, critical first, from GET /stats/open with the session token", async () => {
    const fetchMock = answer(200, counts());
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenIncidentsWidget role="support-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Critical")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.textContent?.match(/Critical|High|Medium|Low/)?.[0])).toEqual(["Critical", "High", "Medium", "Low"]);
    expect(screen.getByText("2 open")).toBeTruthy();
    expect(screen.getByText("1 open")).toBeTruthy();
    expect(screen.getAllByText("0 open")).toHaveLength(2);
    expect(screen.getByText("3 open: 1 not yet picked up · 1 investigating · 1 mitigated")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Open incidents by severity" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/incident-management/stats/open");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is open", async () => {
    const none = counts({
      total_open: 0,
      by_severity: counts().by_severity.map((r) => ({ ...r, count: 0 })),
      by_status: counts().by_status.map((r) => ({ ...r, count: 0 })),
    });
    vi.stubGlobal("fetch", answer(200, none));
    render(<OpenIncidentsWidget role="support-staff" />);
    expect(await screen.findByText("No open incidents")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => counts() });
    vi.stubGlobal("fetch", fetchMock);
    render(<OpenIncidentsWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load open incidents");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Critical")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet while the API is not mounted (404), and can retry", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<OpenIncidentsWidget role="support-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Incident data is not available yet.");
    expect(alert.textContent).not.toContain("connection");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("says the data is not available yet when the network fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<OpenIncidentsWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Incident data is not available yet.");
  });

  it("offers no retry when access is refused (403) or the session ended (401)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<OpenIncidentsWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(401, {}));
    render(<OpenIncidentsWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("describes each failure as the widget convention says", () => {
    for (const status of [404, 502, 503]) {
      expect(describeFailure(new IncidentManagementApiError(status, ""))).toEqual({
        title: "Incident data is not available yet.",
        retry: true,
      });
    }
    expect(describeFailure(new IncidentManagementApiError(401, "")).retry).toBe(false);
    expect(describeFailure(new IncidentManagementApiError(403, "")).retry).toBe(false);
    expect(describeFailure(new IncidentManagementApiError(500, "")).retry).toBe(true);
  });

  it("words the statuses", () => {
    expect(statusLine(counts().by_status)).toBe("1 not yet picked up · 1 investigating · 1 mitigated");
  });
});
