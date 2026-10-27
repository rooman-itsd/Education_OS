import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import type { PendingReport } from "../src/api/client";
import { widgets } from "../src/widgets";
import { PurchaseOrdersPending } from "../src/widgets/PurchaseOrdersPending";

function answer(status: number, body: unknown) {
  return { ok: status < 400, status, statusText: "", json: async () => body };
}

/** Stubs fetch with one response per call, in order. */
function stubFetch(...responses: ReturnType<typeof answer>[]) {
  const fetchMock = vi.fn();
  for (const r of responses) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastCall(fetchMock: ReturnType<typeof vi.fn>) {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit];
  return { url, headers: init.headers as Record<string, string> };
}

/** The summary figure with this label: its <div> holding the dt and dd. */
function figure(label: string): HTMLElement {
  return screen.getByText(label, { selector: "dt" }).parentElement as HTMLElement;
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  const expected: [string, string, string, string, ComponentType<WidgetProps>][] = [
    ["procurement.purchase-orders-pending", "procurement:report:read", "2x1", "panel", PurchaseOrdersPending],
  ];

  it("exports the widget the Finance Staff layout names", () => {
    expect(widgets.map((w) => w.id)).toEqual(expected.map((e) => e[0]));
  });

  it.each(expected)("registers %s with permission %s, size %s, kind %s and its component", (id, permission, size, kind, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w).toBeTruthy();
    expect(w?.permission).toBe(permission);
    expect(w?.size).toBe(size);
    expect(w?.kind).toBe(kind);
    expect(w?.component).toBe(component);
    expect(w?.title).toBe("Purchase orders pending");
  });
});

const report = (over: Partial<PendingReport> = {}): PendingReport => ({
  awaiting_approval: { count: 4, value: "320000.00" },
  awaiting_delivery: { count: 7, value: "1250000.50" },
  overdue_delivery: { count: 2, value: "180000.00" },
  invoices_awaiting_payment: { count: 3, value: "95000.00" },
  oldest: [
    { id: "p1", number: "PO/2026-27/0012", vendor_name: "Sharma Lab Supplies", status: "issued", total: "150000.00", since: "2026-08-14" },
    { id: "p2", number: "PO/2026-27/0019", vendor_name: "Deccan Furniture Works", status: "partially_received", total: "30000.00", since: "2026-09-02" },
    { id: "p3", number: "PO/2026-27/0027", vendor_name: "Infotech Systems", status: "submitted", total: "220000.00", since: "2026-10-01" },
    { id: "p4", number: "PO/2026-27/0031", vendor_name: "City Stationers", status: "returned", total: "4500.00", since: "2026-10-20" },
  ],
  ...over,
});

const nothing = (over: Partial<PendingReport> = {}): PendingReport =>
  report({
    awaiting_approval: { count: 0, value: "0.00" },
    awaiting_delivery: { count: 0, value: "0.00" },
    overdue_delivery: { count: 0, value: "0.00" },
    invoices_awaiting_payment: { count: 0, value: "0.00" },
    oldest: [],
    ...over,
  });

describe("procurement.purchase-orders-pending", () => {
  it("shows the four counts with their values from GET /reports/purchase-orders-pending", async () => {
    const fetchMock = stubFetch(answer(200, report()));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("Awaiting approval")).toBeTruthy();
    expect(figure("Awaiting approval").textContent).toBe("Awaiting approval4₹3,20,000.00");
    expect(figure("Awaiting delivery").textContent).toBe("Awaiting delivery7₹12,50,000.50");
    expect(figure("Overdue deliveries").textContent).toBe("Overdue deliveries2₹1,80,000.00");
    expect(figure("Invoices awaiting payment").textContent).toBe("Invoices awaiting payment3₹95,000.00");
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe("/api/v1/procurement/reports/purchase-orders-pending");
    expect(headers.Authorization).toBe("Bearer test-token");
  });

  it("flags overdue deliveries in danger when there are any", async () => {
    stubFetch(answer(200, report()));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(await screen.findByText("2 deliveries overdue")).toBeTruthy();
    expect(screen.getByText("2 deliveries overdue").className).toContain("eos-badge--danger");
    expect(figure("Overdue deliveries").hasAttribute("data-warn")).toBe(true);
    expect(figure("Awaiting approval").hasAttribute("data-warn")).toBe(false);
    expect(figure("Awaiting delivery").hasAttribute("data-warn")).toBe(false);
    expect(figure("Invoices awaiting payment").hasAttribute("data-warn")).toBe(false);
  });

  it("says one delivery overdue in the singular", async () => {
    stubFetch(answer(200, report({ overdue_delivery: { count: 1, value: "5000.00" } })));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect((await screen.findByText("1 delivery overdue")).className).toContain("eos-badge--danger");
  });

  it("does not flag overdue deliveries when there are none", async () => {
    stubFetch(answer(200, report({ overdue_delivery: { count: 0, value: "0.00" } })));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(await screen.findByText("Overdue deliveries")).toBeTruthy();
    expect(figure("Overdue deliveries").hasAttribute("data-warn")).toBe(false);
    expect(screen.queryByText(/overdue$/)).toBeNull();
    expect(document.querySelector(".eos-procurement__alert")).toBeNull();
  });

  it("lists the oldest pending orders with vendor, date, total and status label, in the report's order", async () => {
    stubFetch(answer(200, report()));
    render(<PurchaseOrdersPending role="finance-staff" />);
    const list = await screen.findByRole("list", { name: "Oldest pending orders" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(within(rows[0]!).getByText("PO/2026-27/0012")).toBeTruthy();
    expect(within(rows[0]!).getByText("Sharma Lab Supplies")).toBeTruthy();
    expect(within(rows[0]!).getByText("Pending since 14 Aug 2026")).toBeTruthy();
    expect(within(rows[0]!).getByText("₹1,50,000.00")).toBeTruthy();
    expect(within(rows[0]!).getByText("Issued").className).toContain("eos-badge--info");
    expect(within(rows[1]!).getByText("Partly received").className).toContain("eos-badge--info");
    expect(within(rows[2]!).getByText("Submitted").className).toContain("eos-badge--warning");
    expect(within(rows[3]!).getByText("Returned").className).toContain("eos-badge--danger");
    expect(within(rows[3]!).getByText("₹4,500.00")).toBeTruthy();
    expect(rows.map((r) => within(r).getByText(/^PO\//).textContent)).toEqual([
      "PO/2026-27/0012",
      "PO/2026-27/0019",
      "PO/2026-27/0027",
      "PO/2026-27/0031",
    ]);
  });

  it("shows the counts without a list when no order is among the oldest", async () => {
    stubFetch(answer(200, report({ oldest: [] })));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(await screen.findByText("Awaiting approval")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByText("No purchase orders pending")).toBeNull();
  });

  it("renders a report without oldest instead of unmounting the dashboard", async () => {
    const { oldest: _omitted, ...withoutOldest } = report();
    stubFetch(answer(200, withoutOldest));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(await screen.findByText("₹3,20,000.00")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an empty state when nothing is pending", async () => {
    stubFetch(answer(200, nothing()));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(await screen.findByText("No purchase orders pending")).toBeTruthy();
    expect(screen.getByText("Orders awaiting approval or delivery and invoices awaiting payment appear here.")).toBeTruthy();
    expect(screen.queryByText("Awaiting approval")).toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("is not empty while one count is above zero", async () => {
    stubFetch(answer(200, nothing({ invoices_awaiting_payment: { count: 1, value: "12000.00" } })));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect(await screen.findByText("₹12,000.00")).toBeTruthy();
    expect(screen.queryByText("No purchase orders pending")).toBeNull();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { code: "internal", message: "Database unavailable" }), answer(200, report()));
    render(<PurchaseOrdersPending role="finance-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load procurement data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹3,20,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(lastCall(fetchMock).url).toBe("/api/v1/procurement/reports/purchase-orders-pending");
  });

  it("shows an error when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, report()));
    vi.stubGlobal("fetch", fetchMock);
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Procurement data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹3,20,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([404, 502, 503])("says the data is not available yet on %i, with a retry", async (status) => {
    stubFetch(answer(status, {}));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Procurement data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: "Not authenticated" }));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("offers no retry when the viewer lacks the permission", async () => {
    stubFetch(answer(403, { code: "forbidden", message: "Forbidden" }));
    render(<PurchaseOrdersPending role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });
});
