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
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load low stock");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Rosin")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
