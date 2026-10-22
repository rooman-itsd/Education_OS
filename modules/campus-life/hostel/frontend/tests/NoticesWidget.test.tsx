import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Notice } from "../src/api/client";
import { widgets } from "../src/widgets";
import { NOTICE_LIMIT, NoticesWidget } from "../src/widgets/NoticesWidget";

const notice = (over: Partial<Notice> = {}): Notice => ({
  id: "n1",
  organisation_id: "o1",
  hostel_id: "h1",
  title: "Water cut",
  body: "No water from 2 to 4 pm",
  expires_at: null,
  published_at: "2026-10-12T08:00:00+00:00",
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

describe("hostel.notices widget", () => {
  it("is exported with the id, permission and size the Student layout expects", () => {
    const w = widgets.find((x) => x.id === "hostel.notices");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("hostel:self:read");
    expect(w?.size).toBe("2x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(NoticesWidget);
  });

  it("lists the caller's notices from GET /me/notices with the session token", async () => {
    const fetchMock = answer(200, [
      notice(),
      notice({ id: "n2", hostel_id: null, title: "Diwali holiday", expires_at: "2026-10-20T00:00:00+00:00" }),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<NoticesWidget role="student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Water cut")).toBeTruthy();
    expect(screen.getByText("Diwali holiday")).toBeTruthy();
    expect(screen.getAllByText("All hostels")).toHaveLength(1); // only the notice to every hostel is tagged
    expect(screen.getByRole("list", { name: "Hostel notices" })).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/hostel/me/notices?limit=${NOTICE_LIMIT}`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when there are no notices", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<NoticesWidget role="student" />);
    expect(await screen.findByText("No hostel notices right now")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => [notice()] });
    vi.stubGlobal("fetch", fetchMock);
    render(<NoticesWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load hostel notices");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Water cut")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
