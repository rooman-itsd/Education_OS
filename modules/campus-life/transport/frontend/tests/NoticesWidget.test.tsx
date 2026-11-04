import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Notice } from "../src/api/client";
import { widgets } from "../src/widgets";
import { NOTICE_LIMIT, NoticesWidget } from "../src/widgets/NoticesWidget";

const notice = (over: Partial<Notice> = {}): Notice => ({
  id: "n1",
  organisation_id: "o1",
  route_id: "r1",
  route_code: "R1",
  kind: "delay",
  title: "Bus late today",
  body: "Running 15 minutes late",
  expires_at: null,
  published_at: "2026-10-27T08:00:00+00:00",
  status: "current",
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

describe("transport.notices widget", () => {
  it("is exported with the id, permission and size the Student layout expects", () => {
    const w = widgets.find((x) => x.id === "transport.notices");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("transport:self:read");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(NoticesWidget);
  });

  it("lists the caller's notices from GET /me/notices with the session token", async () => {
    const fetchMock = answer(200, [
      notice(),
      notice({
        id: "n2",
        route_id: null,
        route_code: null,
        kind: "general",
        title: "No service on Diwali",
        expires_at: "2026-11-09T00:00:00+00:00",
      }),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<NoticesWidget role="student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Bus late today")).toBeTruthy();
    expect(screen.getByText("No service on Diwali")).toBeTruthy();
    expect(screen.getByText("Delay")).toBeTruthy();
    expect(screen.getByText("Notice")).toBeTruthy();
    expect(screen.getByText(/Route R1/)).toBeTruthy();
    expect(screen.getByText(/All routes/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Transport notices" })).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/transport/me/notices?limit=${NOTICE_LIMIT}`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when there are no notices", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<NoticesWidget role="student" />);
    expect(await screen.findByText("No transport notices right now")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => [notice()] });
    vi.stubGlobal("fetch", fetchMock);
    render(<NoticesWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Transport data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Bus late today")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([
    [401, "Sign in again to see this."],
    [403, "You do not have access to this."],
  ])("on %i says why and offers no retry", async (status, text) => {
    vi.stubGlobal("fetch", answer(status, {}));
    render(<NoticesWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain(text);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("on another server error offers a retry", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(<NoticesWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load transport notices");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
