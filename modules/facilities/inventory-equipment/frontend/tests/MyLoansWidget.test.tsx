import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Loan, LoanPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MyLoansWidget } from "../src/widgets/MyLoansWidget";

const loan = (over: Partial<Loan>): Loan => ({
  id: "l-1",
  borrower_id: "u-1",
  status: "on_loan",
  lines: [{ id: "ln-1", item_id: "i-1", item_name: "Violin", quantity: 1, unit_tag: "VN-03", status: "out" }],
  due_at: "2026-10-30T10:00:00+00:00",
  days_overdue: 0,
  ...over,
});

const page = (items: Loan[], total = items.length): LoanPage => ({ items, total, page: 1, page_size: 50 });

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

describe("inventory-equipment.my-loans widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "inventory-equipment.my-loans");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("inventory-equipment:loan:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(MyLoansWidget);
  });

  it("lists the caller's open loans from GET /loans, soonest due first, with status in words", async () => {
    const fetchMock = answer(
      200,
      page([
        loan({ id: "l-2", status: "requested", due_at: "2026-11-05T10:00:00+00:00", lines: [{ id: "ln-2", item_id: "i-2", item_name: "Music stand", quantity: 2, status: "waiting" }] }),
        loan({ id: "l-1", status: "overdue", due_at: "2026-10-20T10:00:00+00:00", days_overdue: 3 }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MyLoansWidget role="musician" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Violin VN-03")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("Violin VN-03");
    expect(rows[1]?.textContent).toContain("Music stand × 2");
    expect(screen.getByText("Overdue")).toBeTruthy();
    expect(screen.getByText("Awaiting approval")).toBeTruthy();
    expect(screen.getByText("Was due 20 Oct · 3 days late")).toBeTruthy();
    expect(screen.getByText("Due 5 Nov")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/inventory-equipment/loans?scope=mine&open=true&page_size=50");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows five loans and how many more there are", async () => {
    const many = Array.from({ length: 7 }, (_, i) => loan({ id: `l-${i}`, due_at: `2026-11-1${i}T10:00:00+00:00` }));
    vi.stubGlobal("fetch", answer(200, page(many)));
    render(<MyLoansWidget role="musician" />);
    expect(await screen.findByText("2 more")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
  });

  it("shows an empty state when nothing is on loan", async () => {
    vi.stubGlobal("fetch", answer(200, page([])));
    render(<MyLoansWidget role="musician" />);
    expect(await screen.findByText("Nothing on loan")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => page([loan({})]) });
    vi.stubGlobal("fetch", fetchMock);
    render(<MyLoansWidget role="musician" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load your loans");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Violin VN-03")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("survives a loan whose due date is missing or malformed and whose item was deleted", async () => {
    const { loanItems, shortDate } = await import("../src/api/client");
    expect(shortDate("not-a-date")).toBe("—");
    expect(shortDate(null)).toBe("—");
    expect(shortDate("2026-10-30T10:00:00+00:00")).toBe("30 Oct");
    expect(loanItems({ lines: [{ item_name: null, unit_tag: "VN-03", quantity: 1 }] } as never)).toBe("Item VN-03");
    expect(loanItems({ lines: [{ item_name: "Reed", unit_tag: null, quantity: 2.5 }] } as never)).toBe("Reed × 2.5");
  });
});
