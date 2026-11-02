import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { MyRolesWidget } from "../src/widgets/MyRolesWidget";
import { answer, myRole, page } from "./helpers";

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("productions.my-roles widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "productions.my-roles");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("productions:role:read-own");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(MyRolesWidget);
  });

  it("lists the caller's own parts from GET /my-roles with the session token", async () => {
    const fetchMock = answer(
      200,
      page([myRole({ role_id: "r-1" }), myRole({ role_id: "r-2", role_name: "Olivia", role_status: "confirmed" })]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MyRolesWidget role="actor" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Viola · Twelfth Night")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "Your parts" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/productions/my-roles?limit=50");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says in words which parts still need an answer", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page([myRole({ role_id: "r-1", role_status: "invited" }), myRole({ role_id: "r-2", role_status: "confirmed" })])),
    );
    render(<MyRolesWidget role="dancer" />);
    expect(await screen.findByText("Reply needed")).toBeTruthy();
    expect(screen.getByText("Confirmed")).toBeTruthy();
  });

  it("says a production has no dates yet instead of showing a dash", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page([myRole({ starts_at: null, call_time: null, status: "in_preparation" })])),
    );
    render(<MyRolesWidget role="actor" />);
    expect(await screen.findByText("In preparation, no dates yet")).toBeTruthy();
  });

  it("caps the list and counts the rest", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page(Array.from({ length: 8 }, (_, i) => myRole({ role_id: `r-${i}`, role_name: `Part ${i}` })))),
    );
    render(<MyRolesWidget role="actor" />);
    expect(await screen.findByText("3 more")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(6); // five parts and the "more" row
  });

  it("shows an empty state when the caller holds no part", async () => {
    vi.stubGlobal("fetch", answer(200, page([])));
    render(<MyRolesWidget role="actor" />);
    expect(await screen.findByText("No parts yet")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => page([myRole()]) });
    vi.stubGlobal("fetch", fetchMock);
    render(<MyRolesWidget role="actor" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Production data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Viola · Twelfth Night")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the session has expired (401) or access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<MyRolesWidget role="actor" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(401, { detail: "token expired" }));
    render(<MyRolesWidget role="actor" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("names a server fault without blaming the connection", async () => {
    vi.stubGlobal("fetch", answer(500, { detail: "boom" }));
    render(<MyRolesWidget role="actor" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load your parts");
    expect(alert.textContent).not.toContain("connection");
  });
});
