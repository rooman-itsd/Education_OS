import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { widgets } from "../src/widgets";
import { InPreparationWidget } from "../src/widgets/InPreparationWidget";
import { answer, page, preparing } from "./helpers";

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("productions.in-preparation widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "productions.in-preparation");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("productions:task:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(InPreparationWidget);
  });

  it("lists what is being got ready from GET /in-preparation with the session token", async () => {
    const fetchMock = answer(200, page([preparing(), preparing({ id: "p-2", title: "Moot Final" })]));
    vi.stubGlobal("fetch", fetchMock);
    render(<InPreparationWidget role="director" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Degree Show")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("list", { name: "In preparation" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/productions/in-preparation?limit=5");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("says what is outstanding in words, overdue first", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page([preparing({ tasks_open: 3, tasks_total: 7, tasks_overdue: 2, cast_unanswered: 1 })])),
    );
    render(<InPreparationWidget role="choreographer" />);
    const row = await screen.findByRole("listitem");
    expect(row.textContent).toContain("2 overdue");
    expect(row.textContent).toContain("3 of 7 tasks open");
    expect(row.textContent).toContain("1 invitation unanswered");
  });

  it("uses the plural only when there is more than one invitation", async () => {
    vi.stubGlobal("fetch", answer(200, page([preparing({ tasks_open: 0, cast_unanswered: 2 })])));
    render(<InPreparationWidget role="studio-instructor" />);
    expect((await screen.findByRole("listitem")).textContent).toContain("2 invitations unanswered");
  });

  it("says a production with nothing outstanding is ready to schedule", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page([preparing({ tasks_open: 0, tasks_total: 4, tasks_overdue: 0, cast_unanswered: 0 })])),
    );
    render(<InPreparationWidget role="director" />);
    expect((await screen.findByRole("listitem")).textContent).toContain("ready to schedule");
  });

  it("says when a production has no date yet rather than leaving the badge empty", async () => {
    vi.stubGlobal("fetch", answer(200, page([preparing({ starts_at: null })])));
    render(<InPreparationWidget role="director" />);
    expect(await screen.findByText("No date")).toBeTruthy();
  });

  it("counts the rest in a last row", async () => {
    vi.stubGlobal(
      "fetch",
      answer(200, page(Array.from({ length: 5 }, (_, i) => preparing({ id: `p-${i}`, title: `Show ${i}` })), 8)),
    );
    render(<InPreparationWidget role="director" />);
    expect(await screen.findByText("3 more in preparation")).toBeTruthy();
  });

  it("shows an empty state when nothing is in preparation", async () => {
    vi.stubGlobal("fetch", answer(200, page([])));
    render(<InPreparationWidget role="director" />);
    expect(await screen.findByText("Nothing in preparation")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => page([preparing()]) });
    vi.stubGlobal("fetch", fetchMock);
    render(<InPreparationWidget role="director" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Production data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Degree Show")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<InPreparationWidget role="director" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
