import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Loan } from "../src/api/client";
import { widgets } from "../src/widgets";
import { LoansWidget } from "../src/widgets/LoansWidget";

const loan = (over: Partial<Loan> = {}): Loan => ({
  id: "l1",
  organisation_id: "o1",
  copy_id: "c1",
  title_id: "t1",
  title: "Gray's Anatomy",
  person_id: "p1",
  issued_at: "2026-10-29T08:00:00+00:00",
  due_on: "2026-11-12",
  status: "active",
  renewals: 0,
  renewals_left: 1,
  overdue: false,
  fine_accrued: "0.00",
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

describe("library.loans widget", () => {
  it("is exported with the id, permission, size and kind the Student layout expects", () => {
    const w = widgets.find((x) => x.id === "library.loans");
    expect(w?.permission).toBe("library:self:read");
    expect(w?.size).toBe("1x1");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(LoansWidget);
  });

  it("lists the caller's loans from GET /me/loans with the session token, flagging overdue ones", async () => {
    const fetchMock = answer(200, [
      loan({ id: "l1", title: "Robbins Pathology", due_on: "2026-11-01", overdue: true, fine_accrued: "6.00", renewals_left: 0 }),
      loan({ id: "l2" }),
    ]);
    vi.stubGlobal("fetch", fetchMock);
    render(<LoansWidget role="student" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Robbins Pathology")).toBeTruthy();
    expect(screen.getByText("Gray's Anatomy")).toBeTruthy();
    expect(screen.getByText("Overdue · 6.00")).toBeTruthy(); // the exact amount from the API, not a float
    expect(screen.getAllByText(/Overdue/)).toHaveLength(1);
    expect(screen.getByText(/0 renewals left/)).toBeTruthy();
    expect(screen.getByText(/1 renewal left/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Library loans" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/library/me/loans");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is on loan", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<LoansWidget role="student" />);
    expect(await screen.findByText("No books on loan")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => [loan()] });
    vi.stubGlobal("fetch", fetchMock);
    render(<LoansWidget role="student" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load your library loans");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Gray's Anatomy")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
