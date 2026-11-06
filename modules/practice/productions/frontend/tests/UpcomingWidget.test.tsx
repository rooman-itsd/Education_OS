import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { UpcomingWidget } from "../src/widgets/UpcomingWidget";
import { answer, entry, page } from "./helpers";

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("productions.upcoming widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "productions.upcoming");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("productions:production:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(UpcomingWidget);
  });

  it("lists the next productions from GET /upcoming with the session token", async () => {
    const fetchMock = answer(200, page([entry(), entry({ id: "p-2", title: "Jazz Night", kind: "recital" })]));
    vi.stubGlobal("fetch", fetchMock);
    render(<UpcomingWidget role="musician" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Twelfth Night")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "Coming up" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/productions/upcoming?limit=5");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("names the kind in the viewer's words and shows where and when", async () => {
    vi.stubGlobal("fetch", answer(200, page([entry({ kind: "competition", venue: "Court Room 1" })])));
    render(<UpcomingWidget role="law-student" />);
    const row = await screen.findByRole("listitem");
    expect(row.textContent).toContain("Competition");
    expect(row.textContent).toContain("Court Room 1");
  });

  it("shows no cast figures: a learner sees what is on, not who is in it", async () => {
    vi.stubGlobal("fetch", answer(200, page([entry({ cast_confirmed: 4 })])));
    render(<UpcomingWidget role="artist" />);
    await screen.findByText("Twelfth Night");
    expect(screen.queryByText("4 confirmed")).toBeNull();
  });

  it("counts the rest in a last row", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page(Array.from({ length: 5 }, (_, i) => entry({ id: `p-${i}`, title: `Show ${i}` })), 12)),
    );
    render(<UpcomingWidget role="management" />);
    expect(await screen.findByText("7 more")).toBeTruthy();
  });

  it("shows an empty state when nothing is coming up", async () => {
    vi.stubGlobal("fetch", answer(200, page([])));
    render(<UpcomingWidget role="artist" />);
    expect(await screen.findByText("Nothing coming up")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => page([entry()]) });
    vi.stubGlobal("fetch", fetchMock);
    render(<UpcomingWidget role="artist" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Production data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Twelfth Night")).toBeTruthy();
  });

  it("offers no retry when the session has expired (401)", async () => {
    vi.stubGlobal("fetch", answer(401, { detail: "token expired" }));
    render(<UpcomingWidget role="artist" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
