import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import { getReconciliationSummary, type ReconciliationSummary } from "../src/api/client";
import { widgets } from "../src/widgets";
import { moment, rupees } from "../src/widgets/format";
import { Reconciliation } from "../src/widgets/Reconciliation";

const URL_SUMMARY = "/api/v1/payment-sbiepay/reconciliation/summary";

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
    ["payment-sbiepay.reconciliation", "payment-sbiepay:payment:read", "1x1", "panel", Reconciliation],
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
    expect(w?.title).toBe("Online payments reconciliation");
  });
});

describe("format", () => {
  it("formats decimal strings as Indian rupees without floating point", () => {
    expect(rupees("20000.00")).toBe("₹20,000.00");
    expect(rupees("1250000.5")).toBe("₹12,50,000.50");
    expect(rupees("0.00")).toBe("₹0.00");
    expect(rupees("0.1")).toBe("₹0.10");
    expect(rupees(undefined)).toBe("—");
    expect(rupees("abc")).toBe("—");
  });

  it("formats a run time in the viewer's time zone (tests run in Asia/Kolkata)", () => {
    expect(moment("2026-10-30T08:35:12.123456+00:00")).toBe("30 Oct 2026, 14:05");
    expect(moment(null)).toBeNull();
    expect(moment("not a date")).toBeNull();
  });
});

const summary = (over: Partial<ReconciliationSummary> = {}): ReconciliationSummary => ({
  date: "2026-10-30",
  succeeded: { count: 12, amount: "245000.00" },
  pending: { count: 3, amount: "45000.50" },
  failed: { count: 2 },
  settled: { count: 9, amount: "200000.00" },
  mismatches: 0,
  last_run_at: "2026-10-30T08:35:12.123456+00:00",
  ...over,
});

const nothing = (over: Partial<ReconciliationSummary> = {}): ReconciliationSummary =>
  summary({
    succeeded: { count: 0, amount: "0.00" },
    pending: { count: 0, amount: "0.00" },
    failed: { count: 0 },
    settled: { count: 0, amount: "0.00" },
    mismatches: 0,
    last_run_at: null,
    ...over,
  });

describe("payment-sbiepay.reconciliation", () => {
  it("shows the day's figures with their amounts from GET /reconciliation/summary", async () => {
    const fetchMock = stubFetch(answer(200, summary()));
    render(<Reconciliation role="finance-staff" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    expect(await screen.findByText("Succeeded")).toBeTruthy();
    expect(figure("Succeeded").textContent).toBe("Succeeded12₹2,45,000.00");
    expect(figure("Settled").textContent).toBe("Settled9₹2,00,000.00");
    expect(figure("Pending").textContent).toBe("Pending3₹45,000.50");
    expect(figure("Failed").textContent).toBe("Failed2");
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe(URL_SUMMARY);
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("names the day and its regions, with the figures in a description list", async () => {
    stubFetch(answer(200, summary()));
    render(<Reconciliation role="finance-staff" />);
    const payments = await screen.findByRole("region", { name: "Payments" });
    expect(within(payments).getByRole("heading", { name: "Payments on 30 Oct 2026" })).toBeTruthy();
    expect(payments.querySelector("dl")?.querySelectorAll("dt")).toHaveLength(4);
    const recon = screen.getByRole("region", { name: "Reconciliation" });
    expect(within(recon).getByRole("heading", { name: "Reconciliation" })).toBeTruthy();
  });

  it("says when the day was last reconciled and that it found no mismatches", async () => {
    stubFetch(answer(200, summary()));
    render(<Reconciliation role="finance-staff" />);
    const recon = await screen.findByRole("region", { name: "Reconciliation" });
    expect(within(recon).getByText("No mismatches").className).toContain("eos-badge--success");
    expect(within(recon).getByText("Last reconciled 30 Oct 2026, 14:05")).toBeTruthy();
    expect(screen.queryByText("Not reconciled yet")).toBeNull();
    expect(screen.queryByText(/mismatch(es)?$/, { selector: ".eos-badge--danger" })).toBeNull();
  });

  it("flags the latest run's mismatches in danger", async () => {
    stubFetch(answer(200, summary({ mismatches: 3 })));
    render(<Reconciliation role="finance-staff" />);
    expect((await screen.findByText("3 mismatches")).className).toContain("eos-badge--danger");
    expect(screen.queryByText("No mismatches")).toBeNull();
    expect(screen.getByText("Last reconciled 30 Oct 2026, 14:05")).toBeTruthy();
  });

  it("says one mismatch in the singular", async () => {
    stubFetch(answer(200, summary({ mismatches: 1 })));
    render(<Reconciliation role="finance-staff" />);
    expect((await screen.findByText("1 mismatch")).className).toContain("eos-badge--danger");
  });

  it("says the day is not reconciled yet when there is no run", async () => {
    stubFetch(answer(200, summary({ last_run_at: null, mismatches: 0 })));
    render(<Reconciliation role="finance-staff" />);
    const recon = await screen.findByRole("region", { name: "Reconciliation" });
    expect(within(recon).getByText("Not reconciled yet").className).toContain("eos-badge--warning");
    expect(screen.queryByText(/^Last reconciled/)).toBeNull();
    expect(screen.queryByText("No mismatches")).toBeNull();
    expect(figure("Succeeded").textContent).toBe("Succeeded12₹2,45,000.00");
  });

  it("shows an empty state when the day has no payment and no run", async () => {
    stubFetch(answer(200, nothing()));
    render(<Reconciliation role="finance-staff" />);
    expect(await screen.findByText("No online payments today")).toBeTruthy();
    expect(screen.getByText("Fee payments made through SBIePay, their settlement and the day's reconciliation appear here.")).toBeTruthy();
    expect(screen.queryByText("Succeeded")).toBeNull();
    expect(screen.queryByText("Not reconciled yet")).toBeNull();
  });

  it.each([
    ["a pending payment", { pending: { count: 1, amount: "1500.00" } }, "₹1,500.00"],
    ["a failed payment", { failed: { count: 1 } }, "Failed1"],
    ["a run with mismatches", { last_run_at: "2026-10-30T08:35:12+00:00", mismatches: 2 }, "2 mismatches"],
    ["a run without payments", { last_run_at: "2026-10-30T08:35:12+00:00" }, "No mismatches"],
  ] as [string, Partial<ReconciliationSummary>, string][])("is not empty with %s", async (_what, over, text) => {
    stubFetch(answer(200, nothing(over)));
    render(<Reconciliation role="finance-staff" />);
    expect(await screen.findByText("Succeeded")).toBeTruthy();
    expect(document.querySelector(".eos-sbiepay")?.textContent).toContain(text);
    expect(screen.queryByText("No online payments today")).toBeNull();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { code: "internal", message: "Database unavailable" }), answer(200, summary()));
    render(<Reconciliation role="finance-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load payment data.");
    expect(alert.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹2,45,000.00")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(lastCall(fetchMock).url).toBe(URL_SUMMARY);
  });

  it("shows an error when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, summary()));
    vi.stubGlobal("fetch", fetchMock);
    render(<Reconciliation role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Payment data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("₹2,45,000.00")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([404, 502, 503])("says the data is not available yet on %i, with a retry", async (status) => {
    stubFetch(answer(status, {}));
    render(<Reconciliation role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Payment data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { detail: "Not authenticated" }));
    render(<Reconciliation role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("offers no retry when the viewer lacks payment-sbiepay:payment:read", async () => {
    stubFetch(answer(403, { detail: "missing permission payment-sbiepay:payment:read" }));
    render(<Reconciliation role="finance-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("asks the client for another day with ?date=YYYY-MM-DD", async () => {
    const fetchMock = stubFetch(answer(200, summary({ date: "2026-10-29" })));
    const got = await getReconciliationSummary("2026-10-29");
    expect(got.date).toBe("2026-10-29");
    expect(lastCall(fetchMock).url).toBe(`${URL_SUMMARY}?date=2026-10-29`);
  });

  it("sends no Authorization header when there is no session token", async () => {
    localStorage.clear();
    const fetchMock = stubFetch(answer(200, summary()));
    render(<Reconciliation role="finance-staff" />);
    expect(await screen.findByText("Succeeded")).toBeTruthy();
    expect(lastCall(fetchMock).headers.Authorization).toBeUndefined();
  });
});
