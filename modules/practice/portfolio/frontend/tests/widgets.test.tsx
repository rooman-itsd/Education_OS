import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Item, ItemPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { MyPortfolioWidget } from "../src/widgets/MyPortfolioWidget";
import { ReviewsPendingWidget } from "../src/widgets/ReviewsPendingWidget";

const item = (over: Partial<Item> = {}): Item => ({
  id: "i-1",
  organisation_id: "o-1",
  type_id: "t-1",
  owner_person_id: "p-1",
  title: "Monsoon Series",
  description: "Six oil studies",
  tags: [],
  attributes: {},
  status: "draft",
  media: [],
  reviews: [],
  submitted_at: null,
  decided_at: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  can: [],
  ...over,
});

const page = (items: Item[]): ItemPage => ({ items, total: items.length, page: 1, page_size: 6 });

function api(body: unknown, status = 200) {
  return vi.fn().mockImplementation(async () => ({ ok: status < 400, status, statusText: "", json: async () => body }));
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("portfolio widgets export", () => {
  it("exports the ids, permissions, kind and size the dashboards and the contract expect", () => {
    expect(widgets.map((w) => w.id)).toEqual(["portfolio.my-portfolio", "portfolio.reviews-pending"]);
    expect(widgets[0]).toMatchObject({ permission: "portfolio:item:read", kind: "list", size: "1x1", component: MyPortfolioWidget });
    expect(widgets[1]).toMatchObject({ permission: "portfolio:review:write", kind: "list", size: "1x1", component: ReviewsPendingWidget });
  });
});

describe("portfolio.my-portfolio", () => {
  it("lists my items with a status badge, asking for scope=mine with the bearer token", async () => {
    const fetchMock = api(
      page([
        item(),
        item({ id: "i-2", title: "Studio Reel", description: null, status: "changes_requested" }),
        item({ id: "i-3", title: "Fashion Lookbook", status: "approved" }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<MyPortfolioWidget role="artist" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.textContent).toContain("Monsoon Series");
    expect(rows[0]?.textContent).toContain("Six oil studies");
    expect(rows[0]?.textContent).toContain("Draft");
    expect(rows[1]?.textContent).toContain("No description");
    expect(rows[1]?.textContent).toContain("Changes Requested");
    expect(rows[2]?.textContent).toContain("Approved");
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/v1/portfolio/items?scope=mine&page_size=6");
    expect((fetchMock.mock.calls[0]?.[1] as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("has an empty state", async () => {
    vi.stubGlobal("fetch", api(page([])));
    render(<MyPortfolioWidget role="artist" />);
    expect(await screen.findByText("No portfolio items yet")).toBeTruthy();
  });

  it.each([
    [401, "Sign in again to see this."],
    [403, "You do not have access to this."],
  ])("does not offer a retry that cannot help (%i)", async (status, text) => {
    vi.stubGlobal("fetch", api({}, status));
    render(<MyPortfolioWidget role="artist" />);
    expect(await screen.findByText(text)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("retries when the service is not available yet", async () => {
    const fetchMock = api({}, 503);
    vi.stubGlobal("fetch", fetchMock);
    render(<MyPortfolioWidget role="artist" />);
    expect(await screen.findByText("Portfolio data is not available yet.")).toBeTruthy();
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, statusText: "", json: async () => page([item()]) }));
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Monsoon Series")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows a generic failure with a retry for other errors", async () => {
    vi.stubGlobal("fetch", api({}, 500));
    render(<MyPortfolioWidget role="artist" />);
    expect(await screen.findByText("Could not load portfolio items")).toBeTruthy();
    expect(screen.getByRole("button")).toBeTruthy();
  });
});

describe("portfolio.reviews-pending", () => {
  it("lists submitted and under-review items from the managed scope, with the submitted date", async () => {
    const fetchMock = api(
      page([
        item({ id: "a", title: "Sculpture Folio", status: "submitted", submitted_at: "2026-11-02T10:00:00Z" }),
        item({ id: "b", title: "Costume Sketches", status: "under_review", submitted_at: null }),
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<ReviewsPendingWidget role="studio-instructor" />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Sculpture Folio");
    expect(rows[0]?.textContent).toContain("Awaiting Review");
    expect(rows[0]?.textContent).toContain(`Submitted ${new Date("2026-11-02T10:00:00Z").toLocaleDateString()}`);
    expect(rows[1]?.textContent).toContain("In Review");
    expect(rows[1]?.textContent).toContain("Submitted recently");
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      "/api/v1/portfolio/items?scope=managed&status=submitted,under_review&page_size=6",
    );
  });

  it("has an empty state", async () => {
    vi.stubGlobal("fetch", api(page([])));
    render(<ReviewsPendingWidget role="design-mentor" />);
    expect(await screen.findByText("No reviews pending")).toBeTruthy();
  });

  it("does not offer a retry on 403, and retries on 404", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<ReviewsPendingWidget role="design-mentor" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    cleanup();
    vi.stubGlobal("fetch", api({}, 404));
    render(<ReviewsPendingWidget role="design-mentor" />);
    expect(await screen.findByText("Portfolio review data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button")).toBeTruthy();
  });
});
