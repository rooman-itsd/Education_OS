import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Loan, LoanPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { OverdueLoansWidget } from "../src/widgets/OverdueLoansWidget";

const loan = (over: Partial<Loan>): Loan => ({
  id: "l-1",
  borrower_id: "u-1",
  status: "overdue",
  lines: [{ id: "ln-1", item_id: "i-1", item_name: "Tripod", quantity: 1, status: "out" }],
  due_at: "2026-10-20T10:00:00+00:00",
  days_overdue: 1,
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

describe("inventory-equipment.overdue-loans widget", () => {
  it("is exported with the id and permission the Equipment Manager layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "inventory-equipment.overdue-loans");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("inventory-equipment:loan:read-all");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(OverdueLoansWidget);
  });

  it("lists overdue loans from GET /loans, longest late first", async () => {
    const fetchMock = answer(
      200,
      page([
        loan({ id: "l-1", days_overdue: 1 }),
        loan({ id: "l-2", days_overdue: 9, due_at: "2026-10-12T10:00:00+00:00", lines: [{ id: "ln-2", item_id: "i-2", item_name: "Cello", quantity: 1, unit_tag: "CE-01", status: "out" }] }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<OverdueLoansWidget role="equipment-manager" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Cello CE-01")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("Cello CE-01");
    expect(rows[1]?.textContent).toContain("Tripod");
    expect(screen.getByText("9 days late")).toBeTruthy();
    expect(screen.getByText("1 day late")).toBeTruthy();
    expect(screen.getByText("Due 12 Oct")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Overdue loans" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/inventory-equipment/loans?scope=managed&status=overdue&page_size=50");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is overdue", async () => {
    vi.stubGlobal("fetch", answer(200, page([])));
    render(<OverdueLoansWidget role="equipment-manager" />);
    expect(await screen.findByText("No overdue loans")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => page([loan({})]) });
    vi.stubGlobal("fetch", fetchMock);
    render(<OverdueLoansWidget role="equipment-manager" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load overdue loans");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Tripod")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
