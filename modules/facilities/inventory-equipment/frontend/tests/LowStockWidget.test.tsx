import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LowStockLine } from "../src/api/client";
import { widgets } from "../src/widgets";
import { LowStockWidget } from "../src/widgets/LowStockWidget";

const lines: LowStockLine[] = [
  { item_id: "i-1", item_name: "Guitar strings", available: 0, reorder_level: 10, reorder_quantity: 40, unit_of_measure: "sets" },
  { item_id: "i-2", item_name: "Rosin", available: 3, reorder_level: 5, reorder_quantity: 20, unit_of_measure: "pcs" },
];

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

describe("inventory-equipment.low-stock widget", () => {
  it("is exported with the id and permission the role layouts and the contract expect", () => {
    const w = widgets.find((x) => x.id === "inventory-equipment.low-stock");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("inventory-equipment:stock:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(LowStockWidget);
  });

  it("lists low items from GET /low-stock with the session token, out of stock in words", async () => {
    const fetchMock = answer(200, lines);
    vi.stubGlobal("fetch", fetchMock);
    render(<LowStockWidget role="facility-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Guitar strings")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("Out of stock")).toBeTruthy();
    expect(screen.getByText("3 pcs left")).toBeTruthy();
    expect(screen.getByText("Reorder level 5 pcs")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Items low on stock" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/inventory-equipment/low-stock");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state when nothing is low", async () => {
    vi.stubGlobal("fetch", answer(200, []));
    render(<LowStockWidget role="facility-staff" />);
    expect(await screen.findByText("Stock is healthy")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => lines });
    vi.stubGlobal("fetch", fetchMock);
    render(<LowStockWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Inventory data is not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Rosin")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("offers no retry when the session has expired (401) or access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<LowStockWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", answer(401, { detail: "token expired" }));
    render(<LowStockWidget role="facility-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("names a server fault without blaming the connection, and still retries", async () => {
    vi.stubGlobal("fetch", answer(500, { detail: "boom" }));
    render(<LowStockWidget role="facility-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Could not load low stock");
    expect(alert.textContent).not.toContain("connection");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("formats quantities without float noise and caps the list at six rows", async () => {
    const many: LowStockLine[] = [
      { ...lines[1]!, item_id: "f", item_name: "Flour", available: 10.200000000000001, reorder_level: 12.5, unit_of_measure: "kg" },
      ...Array.from({ length: 8 }, (_, i) => ({ ...lines[1]!, item_id: `x${i}`, item_name: `Item ${i}` })),
    ];
    vi.stubGlobal("fetch", answer(200, many));
    render(<LowStockWidget role="facility-staff" />);
    expect(await screen.findByText("10.2 kg left")).toBeTruthy();
    expect(screen.getByText("Reorder level 12.5 kg")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(7); // six rows and the "more" row
    expect(screen.getByText("3 more")).toBeTruthy();
  });
});
