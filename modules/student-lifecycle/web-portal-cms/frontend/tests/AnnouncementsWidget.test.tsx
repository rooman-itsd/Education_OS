import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Announcement, AnnouncementPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { AnnouncementsWidget, excerpt } from "../src/widgets/AnnouncementsWidget";

const announcement = (over: Partial<Announcement>): Announcement => ({
  id: "a-1",
  title: "Admissions open",
  body: "Apply by 30 November.",
  starts_at: null,
  ends_at: null,
  published_at: "2026-10-28T09:00:00+00:00",
  ...over,
});

const page = (items: Announcement[], total = items.length): AnnouncementPage => ({ items, total, page: 1, page_size: 5 });

function api(body: unknown, status = 200) {
  return vi.fn().mockImplementation(async () => ({ ok: status < 400, status, statusText: "", json: async () => body }));
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("web-portal-cms.announcements", () => {
  it("is exported with the id, permission, kind and size the Applicant layout and the contract expect", () => {
    expect(widgets).toHaveLength(1);
    expect(widgets[0]).toMatchObject({
      id: "web-portal-cms.announcements",
      permission: "web-portal-cms:announcement:read",
      kind: "list",
      size: "1x1",
      component: AnnouncementsWidget,
    });
  });

  it("lists announcements in the API's order with an excerpt and the date, and counts the rest", async () => {
    const fetchMock = api(
      page(
        [
          announcement({ id: "a-1" }),
          announcement({ id: "a-2", title: "Fees due", body: "Pay\n\nby Friday", starts_at: "2026-11-02T00:00:00+00:00" }),
        ],
        7,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AnnouncementsWidget role="applicant" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect(await screen.findByText("Admissions open")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("Apply by 30 November. · 28 Oct 2026");
    expect(rows[1]?.textContent).toContain("Pay by Friday · 2 Nov 2026");
    expect(rows[2]?.textContent).toContain("5 more");
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/v1/web-portal-cms/announcements?page_size=5");
    expect((fetchMock.mock.calls[0]?.[1] as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("shows markup in a body as text, never as HTML", async () => {
    vi.stubGlobal("fetch", api(page([announcement({ title: "<b>Bold?</b>", body: "<img src=x onerror=alert(1)> hello" })])));
    const { container } = render(<AnnouncementsWidget role="applicant" />);
    expect(await screen.findByText("<b>Bold?</b>")).toBeTruthy();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("has an empty state", async () => {
    vi.stubGlobal("fetch", api(page([])));
    render(<AnnouncementsWidget role="applicant" />);
    expect(await screen.findByText("No announcements")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (401)", async () => {
    vi.stubGlobal("fetch", api({}, 401));
    render(<AnnouncementsWidget role="applicant" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("retries when the service is not available yet", async () => {
    const fetchMock = api({}, 503);
    vi.stubGlobal("fetch", fetchMock);
    render(<AnnouncementsWidget role="applicant" />);
    expect(await screen.findByText("Announcements are not available yet.")).toBeTruthy();
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, statusText: "", json: async () => page([announcement({})]) }));
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Admissions open")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("excerpt", () => {
  it("collapses whitespace and cuts long bodies at a word", () => {
    expect(excerpt("  short\n\ntext ")).toBe("short text");
    const long = "word ".repeat(60);
    const cut = excerpt(long, 40);
    expect(cut.endsWith("…")).toBe(true);
    expect(cut.length).toBeLessThanOrEqual(41);
    expect(cut).not.toContain("  ");
  });
});
