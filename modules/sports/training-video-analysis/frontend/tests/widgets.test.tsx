import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TrainingVideo } from "../src/api/client";
import { widgets } from "../src/widgets";
import { duration } from "../src/widgets/format";
import { ReviewsPending, SHOWN } from "../src/widgets/ReviewsPending";

const BASE = "/api/v1/training-video-analysis";

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });

/** Stubs fetch: only `/videos` answers; any other request fails the test. */
function stubApi(videos: Reply | (() => Reply)) {
  const fetchMock = vi.fn(async (input: string, _init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    if (url.pathname.slice(BASE.length) !== "/videos") throw new Error(`unexpected request ${input}`);
    const r = typeof videos === "function" ? videos() : videos;
    return { ok: r.status < 400, status: r.status, statusText: "", json: async () => r.body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const urls = (fetchMock: { mock: { calls: unknown[][] } }) => fetchMock.mock.calls.map((c) => String(c[0]));

const video = (id: string, title: string, recorded_at = "2026-10-20T09:30:00Z", duration_seconds = 245.5): TrainingVideo => ({
  id,
  title,
  uploader_id: "u-1",
  video_url: `https://videos.example/${id}.mp4`,
  duration_seconds,
  recorded_at,
  created_at: recorded_at,
});
const page = <T,>(items: T[], total = items.length) => ({ items, total });

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  it("exports only reviews-pending, with a permission the coach role holds", () => {
    expect(widgets.map((w) => w.id)).toEqual(["training-video-analysis.reviews-pending"]);
    const w = widgets[0]!;
    expect(w.title).toBe("Videos to review");
    expect(w.permission).toBe("training-video-analysis:video:read");
    expect(w.kind).toBe("list");
    expect(w.size).toBe("2x1");
    expect(w.component).toBe(ReviewsPending);
  });

  it("does not export session-plan or training-schedule (the layouts name them under athlete-performance)", () => {
    expect(widgets.map((w) => w.id)).not.toContain("training-video-analysis.session-plan");
    expect(widgets.map((w) => w.id)).not.toContain("training-video-analysis.training-schedule");
  });
});

describe("format", () => {
  it("writes a video's length as m:ss or h:mm:ss", () => {
    expect(duration(245.5)).toBe("4:06");
    expect(duration(59)).toBe("0:59");
    expect(duration(3729)).toBe("1:02:09");
    expect(duration(Number.NaN)).toBe("—");
  });
});

describe("training-video-analysis.reviews-pending", () => {
  const PENDING = `${BASE}/videos?annotated=false&limit=${SHOWN}`;
  const vids = [
    video("v-1", "Sprint mechanics cam A", "2026-10-25T07:00:00Z", 245.5),
    video("v-3", "Block starts", "2026-10-20T07:00:00Z", 3729),
  ];

  it("lists the unannotated videos in the server's order and counts them, in one request", async () => {
    const fetchMock = stubApi(ok(page(vids)));
    render(<ReviewsPending role="coach" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const list = await screen.findByRole("list", { name: "Videos waiting for review" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toContain("Sprint mechanics cam A");
    expect(items[0]?.textContent).toContain("Recorded 25 Oct 2026");
    expect(items[0]?.textContent).toContain("4:06");
    expect(items[1]?.textContent).toContain("Block starts");
    expect(items[1]?.textContent).toContain("1:02:09");
    expect(screen.getByLabelText("Review summary").textContent).toBe("Waiting for review2");
    expect(screen.queryByText(/more$/)).toBeNull();
    expect(urls(fetchMock)).toEqual([PENDING]);
    expect((fetchMock.mock.calls[0]?.[1] as unknown as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it("counts every waiting video from total and says how many more than the rows shown", async () => {
    const shown = Array.from({ length: SHOWN }, (_, i) => video(`v-${i}`, `Video ${i}`));
    const fetchMock = stubApi(ok(page(shown, 23)));
    render(<ReviewsPending role="coach" />);
    const list = await screen.findByRole("list", { name: "Videos waiting for review" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(SHOWN);
    expect(screen.getByLabelText("Review summary").textContent).toBe("Waiting for review23");
    expect(screen.getByText(`and ${23 - SHOWN} videos more`)).toBeTruthy();
    expect(urls(fetchMock)).toEqual([PENDING]);
  });

  it("has an empty state when no video is waiting", async () => {
    const fetchMock = stubApi(ok(page([])));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("No videos waiting for review")).toBeTruthy();
    expect(urls(fetchMock)).toEqual([PENDING]);
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ status: 403, body: { code: "forbidden", message: "no" } });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("asks to sign in again on 401, without a retry", async () => {
    stubApi({ status: 401, body: { detail: "expired" } });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it.each([0, 502, 503])("says the data is not available yet when the service is down (%s)", async (status) => {
    if (status === 0) vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    else stubApi({ status, body: {} });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Training video data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("says the data is not available yet while the backend is missing, and retries", async () => {
    let mounted = false;
    const fetchMock = stubApi(() => (mounted ? ok(page(vids)) : { status: 404, body: { detail: "Not Found" } }));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Training video data is not available yet.")).toBeTruthy();
    mounted = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Videos waiting for review" })).toBeTruthy();
    expect(urls(fetchMock)).toEqual([PENDING, PENDING]);
  });

  it("does not show server wording for other failures", async () => {
    stubApi({ status: 500, body: { code: "boom", message: "Traceback ..." } });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Could not load training video data.")).toBeTruthy();
    expect(screen.queryByText(/Traceback/)).toBeNull();
  });
});
