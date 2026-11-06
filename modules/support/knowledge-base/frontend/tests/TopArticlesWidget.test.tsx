import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TopArticles } from "../src/api/client";
import { widgets } from "../src/widgets";
import { TopArticlesWidget, helpfulLabel } from "../src/widgets/TopArticlesWidget";

const C = "22222222-2222-4222-8222-222222222222";

const top = (over: Partial<TopArticles> = {}): TopArticles => ({
  period: "30d",
  metric: "views",
  items: [
    { article_id: "a1", slug: "wifi", title: "Connect to campus Wi-Fi", type: "how_to", category_id: C, views: 42, helpful_count: 17, not_helpful_count: 3, helpful_share: 0.85 },
    { article_id: "a2", slug: "reset", title: "How do I reset my password?", type: "faq", category_id: C, views: 1, helpful_count: 0, not_helpful_count: 0, helpful_share: null },
  ],
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

describe("knowledge-base.top-articles widget", () => {
  it("is exported with the id and permission the Support Staff layout and the contract expect", () => {
    const w = widgets.find((x) => x.id === "knowledge-base.top-articles");
    expect(w).toBeTruthy();
    expect(w?.permission).toBe("knowledge-base:stats:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(TopArticlesWidget);
  });

  it("lists the most read articles from GET /stats/top-articles with the session token", async () => {
    const fetchMock = answer(200, top());
    vi.stubGlobal("fetch", fetchMock);
    render(<TopArticlesWidget role="support-staff" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Connect to campus Wi-Fi")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows.map((r) => r.textContent?.match(/Wi-Fi|password/)?.[0])).toEqual(["Wi-Fi", "password"]);
    expect(screen.getByText("How-to · 85% found it helpful")).toBeTruthy();
    expect(screen.getByText("FAQ · No votes yet")).toBeTruthy();
    expect(screen.getByText("42 views")).toBeTruthy();
    expect(screen.getByText("1 view")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Top articles" })).toBeTruthy();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/knowledge-base/stats/top-articles");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("shows an empty state with the period when nothing was read", async () => {
    vi.stubGlobal("fetch", answer(200, top({ items: [] })));
    render(<TopArticlesWidget role="support-staff" />);
    expect(await screen.findByText("No article views yet")).toBeTruthy();
    expect(screen.getByText("The articles people read most in the last 30 days appear here.")).toBeTruthy();
  });

  it("shows an error, not a crash, when the request fails, and retries", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, statusText: "", json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => top() });
    vi.stubGlobal("fetch", fetchMock);
    render(<TopArticlesWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load top articles");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Connect to campus Wi-Fi")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("says the data is not available yet while the API is not mounted (404), and can retry", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<TopArticlesWidget role="support-staff" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Knowledge base data is not available yet.");
    expect(alert.textContent).not.toContain("connection");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("offers no retry when access is refused (403)", async () => {
    vi.stubGlobal("fetch", answer(403, { detail: { code: "forbidden" } }));
    render(<TopArticlesWidget role="support-staff" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("words how readers rated an article", () => {
    expect(helpfulLabel({ helpful_count: 0, not_helpful_count: 0, helpful_share: null })).toBe("No votes yet");
    expect(helpfulLabel({ helpful_count: 1, not_helpful_count: 2, helpful_share: 0.3333 })).toBe("33% found it helpful");
    expect(helpfulLabel({ helpful_count: 4, not_helpful_count: 0, helpful_share: 1 })).toBe("100% found it helpful");
  });
});
