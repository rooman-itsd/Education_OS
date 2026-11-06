import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { CalendarWidget } from "../src/widgets/CalendarWidget";
import { answer, entry, page } from "./helpers";

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("productions.calendar widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "productions.calendar");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("productions:production:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(CalendarWidget);
  });

  it("lists what is on from GET /calendar with the session token", async () => {
    const fetchMock = answer(
      200,
      page([entry({ id: "p-1", title: "Twelfth Night" }), entry({ id: "p-2", title: "Jazz Night", venue: "Studio 2" })]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<CalendarWidget role="production-manager" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Twelfth Night")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "What is on" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/productions/calendar?limit=6");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows the venue and start time, and the confirmed cast when there is any", async () => {
    vi.stubGlobal("fetch", answer(200, page([entry({ cast_confirmed: 3 })])));
    render(<CalendarWidget role="stage-manager" />);
    expect((await screen.findByRole("listitem")).textContent).toContain("Main Hall");
    expect(screen.getByText("3 confirmed")).toBeTruthy();
  });

  it("names the kind instead of a zero when nobody has confirmed yet", async () => {
    vi.stubGlobal("fetch", answer(200, page([entry({ kind: "exhibition", cast_confirmed: 0 })])));
    render(<CalendarWidget role="exhibition-manager" />);
    expect(await screen.findByText("Exhibition")).toBeTruthy();
    expect(screen.queryByText("0 confirmed")).toBeNull();
  });

  it("counts the rest of the window in a last row", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page(Array.from({ length: 6 }, (_, i) => entry({ id: `p-${i}`, title: `Show ${i}` })), 9)),
    );
    render(<CalendarWidget role="research-office" />);
    expect(await screen.findByText("3 more in this window")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(7);
  });

  it("shows an empty state when nothing is scheduled", async () => {
    vi.stubGlobal("fetch", answer(200, page([])));
    render(<CalendarWidget role="production-manager" />);
    expect(await screen.findByText("Nothing scheduled")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => page([entry()]) });
    vi.stubGlobal("fetch", fetchMock);
    render(<CalendarWidget role="production-manager" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Production data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Twelfth Night")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the session has expired (401) or access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<CalendarWidget role="production-manager" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(401, { detail: "token expired" }));
    render(<CalendarWidget role="production-manager" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("names a server fault without blaming the connection, and still retries", async () => {
    vi.stubGlobal("fetch", answer(500, { detail: "boom" }));
    render(<CalendarWidget role="production-manager" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load the calendar");
    expect(alert.textContent).not.toContain("connection");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("survives a production with no dates yet", async () => {
    vi.stubGlobal("fetch", answer(200, page([entry({ starts_at: null, ends_at: null, venue: null })])));
    render(<CalendarWidget role="production-manager" />);
    expect(await screen.findByText("Twelfth Night")).toBeTruthy();
    expect(screen.getByRole("listitem").textContent).toContain("—");
  });
});
